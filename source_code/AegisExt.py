"""All UI interaction belongs here. Never edit generated Ui_Aegis.py."""
from contextlib import contextmanager
from pathlib import Path
from decimal import Decimal
import hashlib
import json
import os
from PyQt6.QtCore import Qt,QEvent
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMainWindow,QTableWidgetItem,QHeaderView,QPushButton,QMessageBox,QWidget,QHBoxLayout,QLabel,QSizePolicy
from ui.Ui_Aegis import Ui_MainWindow
from ChartWidgets import DonutChart,TypeBarChart
from AegisService import ApplicationError,validate_payload,summarize
from PyQt6.QtCore import QThread,pyqtSignal
import logging
from TransactionDetailsExt import TransactionDetailsExt

UI_DIR=Path(__file__).resolve().parent/'ui'
FIELD_MAP={'step':'step','type':'type','amount':'amount',
           'oldbalanceOrg':'oldbalance_org','newbalanceOrig':'newbalance_orig',
           'oldbalanceDest':'oldbalance_dest','newbalanceDest':'newbalance_dest'}

@contextmanager
def ui_asset_directory():
    # Generated pixmap paths are relative to the Designer file. Restore the
    # caller's CWD before workers start; no business logic is added to Ui_*.py.
    previous=Path.cwd()
    os.chdir(UI_DIR)
    try:yield
    finally:os.chdir(previous)

class TaskWorker(QThread):
    completed=pyqtSignal(object)
    failed=pyqtSignal(str)

    def __init__(self,function,parent=None):
        super().__init__(parent);self.function=function

    def run(self):
        try:
            result=self.function()
        except ApplicationError as exc:
            self.failed.emit(str(exc))
        except Exception:
            logging.getLogger(__name__).exception('Application task failed')
            self.failed.emit('Không thể hoàn thành thao tác. Kiểm tra cấu hình và kết nối rồi thử lại.')
        else:
            self.completed.emit(result)
        finally:
            self.function=None


class AegisExt(QMainWindow):
    def __init__(self,service,parent=None):
        super().__init__(parent)
        self.service=service
        self.ui=Ui_MainWindow()
        with ui_asset_directory():self.ui.setupUi(self)
        self.user=None;self.rows=[];self._busy=False;self._workers=set();self._generation=0
        self._last_saved_fingerprint=None;self._last_saved_id=None;self.details=None
        self.ui.accountLabel.setTextFormat(Qt.TextFormat.PlainText)
        for edit,asset,position in (
            (self.ui.usernameEdit,'input-user.png',self.ui.usernameEdit.ActionPosition.LeadingPosition),
            (self.ui.passwordEdit,'input-lock.png',self.ui.passwordEdit.ActionPosition.LeadingPosition),
            (self.ui.globalSearchEdit,'search.png',self.ui.globalSearchEdit.ActionPosition.TrailingPosition),
            (self.ui.idFilterEdit,'search.png',self.ui.idFilterEdit.ActionPosition.TrailingPosition)):
            edit.addAction(QIcon(str(UI_DIR/'assets'/asset)),position)
        self.ui.usernameEdit.setMaxLength(50);self.ui.passwordEdit.setMaxLength(1024)
        self.distribution=DonutChart();self.bar_chart=TypeBarChart()
        self.success_chart=DonutChart(True);self.fail_chart=DonutChart(True)
        for host,widget in ((self.ui.distributionHost,self.distribution),
                (self.ui.typeChartHost,self.bar_chart),
                (self.ui.successConfidenceHost,self.success_chart),
                (self.ui.failConfidenceHost,self.fail_chart)):
            layout=host.layout()
            while layout.count():
                item=layout.takeAt(0)
                if item.widget():item.widget().hide();item.widget().deleteLater()
            layout.setContentsMargins(0,0,0,0);layout.addWidget(widget)
        self.forms={prefix:{field:getattr(self.ui,prefix+'_'+field) for field in FIELD_MAP}
                    for prefix in ('success','fail')}
        self.ui.loginButton.clicked.connect(self.login)
        self.ui.passwordEdit.returnPressed.connect(self.login)
        self.ui.usernameEdit.returnPressed.connect(self.ui.passwordEdit.setFocus)
        self.ui.logoutButton.clicked.connect(self.logout)
        self.ui.dashboardButton.clicked.connect(lambda:self.navigate(0))
        self.ui.lookupButton.clicked.connect(lambda:self.navigate(1))
        self.ui.recordsButton.clicked.connect(lambda:self.navigate(3))
        self.ui.quickLookupButton.clicked.connect(lambda:self.navigate(1))
        self.ui.globalSearchEdit.returnPressed.connect(self.global_search)
        for prefix in ('success','fail'):
            getattr(self.ui,prefix+'SubmitButton').clicked.connect(lambda checked=False,p=prefix:self.submit(p))
            getattr(self.ui,prefix+'ClearButton').clicked.connect(self.clear_forms)
            for edit in self.forms[prefix].values():edit.textEdited.connect(self.form_edited)
        self.ui.idFilterEdit.textChanged.connect(self.render_records)
        for cb in (self.ui.typeFilter,self.ui.predictionFilter,self.ui.sortFilter):
            cb.currentIndexChanged.connect(self.render_records)
        self.ui.resetFiltersButton.clicked.connect(self.reset_filters)
        table=self.ui.recordsTable
        table.verticalHeader().hide()
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        table.horizontalHeader().setSectionsMovable(False)
        table.horizontalHeader().setFixedHeight(44)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.column_alignments=(Qt.AlignmentFlag.AlignLeft,Qt.AlignmentFlag.AlignLeft,
            Qt.AlignmentFlag.AlignRight,Qt.AlignmentFlag.AlignHCenter,
            Qt.AlignmentFlag.AlignHCenter,Qt.AlignmentFlag.AlignHCenter,
            Qt.AlignmentFlag.AlignHCenter)
        for index,alignment in enumerate(self.column_alignments):
            table.horizontalHeaderItem(index).setTextAlignment(alignment|Qt.AlignmentFlag.AlignVCenter)
        table.viewport().installEventFilter(self)
        self._size_columns()
        table.cellDoubleClicked.connect(self.open_selected_record)
        self.ui.rootStack.setCurrentIndex(0)
        self.clear_forms();self._clear_data()

    def _size_columns(self):
        table=self.ui.recordsTable
        minimums=(105,105,150,100,140,170,110)
        available=max(table.viewport().width(),sum(minimums))
        extra=available-sum(minimums)
        weights=(.11,.12,.18,.11,.16,.20,.12)
        widths=[minimum+int(extra*weight) for minimum,weight in zip(minimums,weights)]
        widths[-1]+=available-sum(widths)
        for index,width in enumerate(widths):table.setColumnWidth(index,width)

    def eventFilter(self,watched,event):
        if watched is self.ui.recordsTable.viewport() and event.type()==QEvent.Type.Resize:
            self._size_columns()
        return super().eventFilter(watched,event)

    def _set_busy(self,busy):
        self._busy=busy
        controls=(self.ui.loginButton,self.ui.usernameEdit,self.ui.passwordEdit,
                  self.ui.logoutButton,self.ui.dashboardButton,self.ui.lookupButton,
                  self.ui.recordsButton,self.ui.quickLookupButton,
                  self.ui.successSubmitButton,self.ui.failSubmitButton,
                  self.ui.successClearButton,self.ui.failClearButton)
        for control in controls:control.setEnabled(not busy)
        for fields in self.forms.values():
            for edit in fields.values():edit.setEnabled(not busy)
        self.ui.recordsTable.setEnabled(not busy)
        if self.details:self.details.set_busy(busy)
        self.setCursor(Qt.CursorShape.WaitCursor if busy else Qt.CursorShape.ArrowCursor)

    def _run(self,function,callback,on_error=None):
        if self._busy:return
        generation=self._generation
        self._set_busy(True)
        worker=TaskWorker(function,self);self._workers.add(worker)
        def completed(result):
            self._set_busy(False)
            if generation==self._generation:callback(result)
        def failed(message):
            self._set_busy(False)
            if generation==self._generation:
                if on_error:on_error(message)
                QMessageBox.warning(self.details or self,'Không thể hoàn thành',message)
        def finished():
            self._workers.discard(worker);worker.deleteLater()
        worker.completed.connect(completed);worker.failed.connect(failed);worker.finished.connect(finished);worker.start()

    def login(self):
        if self._busy:return
        username=self.ui.usernameEdit.text().strip();password=self.ui.passwordEdit.text()
        if not username or not password:
            QMessageBox.information(self,'Đăng nhập','Vui lòng nhập tên đăng nhập và mật khẩu.');return
        self._clear_data();self.ui.passwordEdit.clear()
        self._run(lambda:self.service.authenticate(username,password),self._logged_in)

    def _logged_in(self,result):
        self.user=result['user']
        self.ui.accountLabel.setText('●  '+str(self.user.get('full_name') or self.user['username']))
        self._apply_data(result);self.ui.rootStack.setCurrentIndex(1);self._show_page(0)

    def _show_page(self,index):
        self.ui.pageStack.setCurrentIndex(index)
        active=0 if index==0 else 2 if index==3 else 1
        for i,button in enumerate((self.ui.dashboardButton,self.ui.lookupButton,self.ui.recordsButton)):
            button.setChecked(i==active)

    def navigate(self,index):
        if self._busy or not self.user:return
        self._show_page(index)
        if index in (0,3):
            user_id=self.user['user_id']
            # Clear cached account data while refreshing; never display stale
            # values as if a failed query succeeded.
            self._clear_data('Đang tải dữ liệu…')
            self._run(lambda:self.service.load_transactions(user_id),self._apply_data,self._load_error)

    def _clear_data(self,message='Chưa có giao dịch. Chọn “Tra cứu giao dịch” để kiểm tra giao dịch mới.'):
        self.rows=[];self._apply_data(dict(rows=[],summary=summarize([])))
        self.ui.emptyMessage.setText(message)
        self.ui.dashboardNote.setText('Thống kê giao dịch của tài khoản đang đăng nhập')

    def _load_error(self,message):
        self.ui.dashboardNote.setText('Không thể tải dữ liệu giao dịch.')
        self.ui.emptyMessage.setText('Không thể tải dữ liệu. Mở lại Tổng quan hoặc Quản lý hồ sơ để thử lại.')
        for widget in (self.ui.totalValue,self.ui.fraudValue,self.ui.legitimateValue,self.ui.fraudRateValue):
            widget.setText('—')
        self.ui.recordsTable.setItem(0,0,QTableWidgetItem('Không thể tải dữ liệu giao dịch. Vui lòng thử lại.'))

    def _apply_data(self,data):
        if data.get('rows') is None:
            self._clear_data('Chưa tải lại được dữ liệu. Mở lại Tổng quan hoặc Quản lý hồ sơ để thử lại.')
            return
        self.rows=list(data['rows']);summary=data['summary']
        for widget,value in zip((self.ui.totalValue,self.ui.fraudValue,self.ui.legitimateValue,self.ui.fraudRateValue),
                (str(summary['total']),str(summary['fraud']),str(summary['legitimate']),f"{summary['fraud_rate']:.1f}%" if summary['total'] else '0%')):
            widget.setText(value)
        self.distribution.set_counts(summary['fraud'],summary['legitimate']);self.bar_chart.set_counts(summary['counts'])
        self.ui.distributionLegend.setText(f'<span style="color:#00595C">■</span> Fraud: {summary["fraud"]} &nbsp; <span style="color:#CADF6B">■</span> Legitimate: {summary["legitimate"]}')
        for card in (self.ui.distributionCard,self.ui.typeChartCard):card.setVisible(bool(self.rows))
        self.ui.emptyMessage.setText('Chưa có giao dịch. Chọn “Tra cứu giao dịch” để kiểm tra giao dịch mới.')
        self.ui.emptyMessage.setVisible(not self.rows)
        self.ui.dashboardNote.setText('Thống kê giao dịch của tài khoản đang đăng nhập')
        self.render_records()

    def global_search(self):
        if self._busy or not self.user:return
        query=self.ui.globalSearchEdit.text().strip();self._show_page(3);self.ui.idFilterEdit.setText(query)
        user_id=self.user['user_id'];self._clear_data('Đang tải dữ liệu…')
        self._run(lambda:self.service.load_transactions(user_id),self._apply_data,self._load_error)

    def reset_filters(self):
        self.ui.idFilterEdit.clear()
        for combo in (self.ui.typeFilter,self.ui.predictionFilter,self.ui.sortFilter):combo.setCurrentIndex(0)
        self.render_records()

    def render_records(self,*_):
        query=self.ui.idFilterEdit.text().strip().casefold();rows=[]
        for row in self.rows:
            if query and query not in str(row['transaction_id']).casefold():continue
            combos=(self.ui.typeFilter,self.ui.predictionFilter)
            if any(combo.currentIndex()!=0 and row.get(key)!=combo.currentText()
                   for combo,key in zip(combos,('type','prediction'))):continue
            rows.append(row)
        rows.sort(key=lambda r:(str(r.get('created_at') or ''),int(r['transaction_id'])),reverse=self.ui.sortFilter.currentIndex()==0)
        table=self.ui.recordsTable;table.clearSpans();table.clearContents();table.setRowCount(len(rows))
        self._visible_rows=rows
        for i,row in enumerate(rows):
            table.setRowHeight(i,62)
            amount=f"{Decimal(str(row['amount'])):,.2f}".replace(',','_').replace('.',',').replace('_','.')+' đ'
            values=(str(row['transaction_id']),row['type'],amount,
                    f"{float(row['fraud_score'])*100:.3f}",row['prediction'],
                    str(row.get('created_at') or '—'))
            for j,value in enumerate(values):
                item=QTableWidgetItem(str(value));item.setToolTip(str(value))
                item.setTextAlignment(self.column_alignments[j]|Qt.AlignmentFlag.AlignVCenter)
                table.setItem(i,j,item)
            wrap=QWidget();layout=QHBoxLayout(wrap);layout.setContentsMargins(8,10,8,10);layout.setSpacing(0)
            positive=row['prediction']=='Fraud'
            color,fill=('#C80D12','#FFF0F0') if positive else ('#208873','#E7F4ED')
            chip=QLabel(row['prediction']);chip.setTextFormat(Qt.TextFormat.PlainText)
            chip.setStyleSheet(f'background:{fill};color:{color};border-radius:5px;padding:5px 9px;font-size:11px;')
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter);chip.setSizePolicy(QSizePolicy.Policy.Fixed,QSizePolicy.Policy.Preferred)
            layout.addStretch();layout.addWidget(chip,0,Qt.AlignmentFlag.AlignVCenter);layout.addStretch();table.setCellWidget(i,4,wrap)
            open_button=QPushButton('Mở hồ sơ ↗');open_button.setCursor(Qt.CursorShape.PointingHandCursor)
            open_button.setStyleSheet('background:#FAFCFC;color:#34516D;border:1px solid #EDF1F3;font-size:10px;padding:5px;')
            open_button.clicked.connect(lambda checked=False,id=row['transaction_id']:self.open_record(id))
            open_button.setFixedHeight(34)
            action_host=QWidget();action_layout=QHBoxLayout(action_host);action_layout.setContentsMargins(8,8,8,8)
            action_layout.addWidget(open_button,0,Qt.AlignmentFlag.AlignVCenter);table.setCellWidget(i,6,action_host)
        self._size_columns()
        if not rows:
            table.setRowCount(1);table.setSpan(0,0,1,7)
            table.setItem(0,0,QTableWidgetItem('Chưa có giao dịch.' if not self.rows else 'Không có hồ sơ phù hợp với bộ lọc.'))

    def open_selected_record(self,row,column):
        if 0<=row<len(self._visible_rows):self.open_record(self._visible_rows[row]['transaction_id'])

    def open_record(self,transaction_id):
        if self._busy or not self.user:return
        user_id=self.user['user_id']
        self._run(lambda:self.service.get_transaction(user_id,transaction_id),self._show_detail)

    def _show_detail(self,row):
        self.details=TransactionDetailsExt(row,self)
        self.details.exec();self.details=None

    def form_edited(self,*_):
        self.ui.successResultBadge.hide();self.ui.failResultBadge.hide()
        self.success_chart.set_probability(None);self.fail_chart.set_probability(None)

    def clear_forms(self):
        for fields in self.forms.values():
            for edit in fields.values():edit.clear()
        self._last_saved_fingerprint=None;self._last_saved_id=None
        self.form_edited()

    def submit(self,prefix):
        if self._busy or not self.user:return
        raw={FIELD_MAP[key]:edit.text().strip() for key,edit in self.forms[prefix].items()}
        try:payload=validate_payload(raw)
        except ApplicationError as exc:QMessageBox.information(self,'Thông tin giao dịch',str(exc));return
        fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()
        if fingerprint==self._last_saved_fingerprint:
            QMessageBox.information(self,'Giao dịch đã lưu',f'Giao dịch #{self._last_saved_id} đã được lưu. Chọn Clear để bắt đầu giao dịch mới.');return
        user_id=self.user['user_id']
        def saved(result):
            self._last_saved_fingerprint=fingerprint;self._last_saved_id=result['transaction_id']
            self._apply_data(result)
            self.show_prediction(result)
            if result.get('refresh_error'):QMessageBox.information(self,'Giao dịch đã lưu',result['refresh_error'])
        self._run(lambda:self.service.predict_and_save(user_id,payload),saved)

    def show_prediction(self,data):
        result=data['result'];success=result.prediction=='Legitimate';prefix='success' if success else 'fail'
        payload=data['payload']
        for fields in self.forms.values():
            for key,edit in fields.items():edit.setText(str(payload[FIELD_MAP[key]]))
        self.success_chart.set_probability(result.fraud_score,success)
        self.fail_chart.set_probability(result.fraud_score,success)
        self.ui.successResultBadge.setVisible(success);self.ui.failResultBadge.setVisible(not success)
        badge=getattr(self.ui,prefix+'ResultBadge')
        badge.setToolTip(f'Đã lưu giao dịch #{data["transaction_id"]} · {result.prediction} · Điểm Fraud {result.fraud_score:.10f} · Ngưỡng {result.threshold:.16f}')
        self._show_page(1 if success else 2)

    def logout(self):
        if self._busy:return
        self._generation+=1;self.user=None;self.clear_forms();self._clear_data();self.reset_filters()
        self.ui.usernameEdit.clear();self.ui.passwordEdit.clear();self.ui.globalSearchEdit.clear()
        self.ui.accountLabel.clear();self.ui.rootStack.setCurrentIndex(0)

    def closeEvent(self,event):
        if any(worker.isRunning() for worker in self._workers):
            event.ignore();QMessageBox.information(self,'Đang xử lý','Vui lòng chờ thao tác đọc/ghi hoàn tất rồi đóng ứng dụng.');return
        event.accept()
