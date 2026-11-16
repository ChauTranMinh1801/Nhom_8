"""Interaction layer. Ui_*.py files remain generated presentation code."""
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import hashlib
import json
import logging
import os
from PyQt6.QtCore import Qt,QEvent,QThread,pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QMainWindow,QTableWidgetItem,QHeaderView,QPushButton,QMessageBox,
    QWidget,QHBoxLayout,QLabel,QSizePolicy,QComboBox,
)
from ui.Ui_Aegis import Ui_MainWindow
from ChartWidgets import DonutChart,TypeBarChart,ActivityLineChart
from AegisService import ApplicationError,validate_payload,summarize,user_display_name
from TransactionDetailsExt import TransactionDetailsExt

UI_DIR=Path(__file__).resolve().parent/'ui'
FIELD_MAP={'step':'step','type':'type','amount':'amount','oldbalanceOrg':'oldbalance_org',
           'newbalanceOrig':'newbalance_orig','oldbalanceDest':'oldbalance_dest','newbalanceDest':'newbalance_dest'}

@contextmanager
def ui_asset_directory():
    previous=Path.cwd();os.chdir(UI_DIR)
    try:yield
    finally:os.chdir(previous)

class TaskWorker(QThread):
    completed=pyqtSignal(object)
    failed=pyqtSignal(str)
    def __init__(self,function,parent=None):
        super().__init__(parent);self.function=function
    def run(self):
        try:result=self.function()
        except ApplicationError as exc:self.failed.emit(str(exc))
        except Exception:
            logging.getLogger(__name__).exception('Application task failed')
            self.failed.emit('Không thể hoàn thành thao tác. Kiểm tra cấu hình và kết nối rồi thử lại.')
        else:self.completed.emit(result)
        finally:self.function=None


def date_text(value):
    if value is None:return '—'
    try:return datetime.fromisoformat(str(value)).strftime('%d/%m/%Y %H:%M:%S')
    except (ValueError,TypeError):return '—'


def money_text(value):
    return f'{Decimal(str(value)):,.2f}'.replace(',','_').replace('.',',').replace('_','.')+' đ'


def score_text(value):
    return f'{float(value)*100:.3f}'.rstrip('0').rstrip('.')+'%'

class AegisExt(QMainWindow):
    def __init__(self,service,parent=None):
        super().__init__(parent);self.service=service;self.ui=Ui_MainWindow()
        with ui_asset_directory():self.ui.setupUi(self)
        arrow=(UI_DIR/'assets/chevron-down.svg').as_posix()
        self.setStyleSheet(self.styleSheet()+f'\nQComboBox::drop-down {{border:none;width:24px;}} QComboBox::down-arrow {{image:url("{arrow}");width:12px;height:12px;}}')
        self.user=None;self.rows=[];self.history_rows=[];self._users=[]
        self._busy=False;self._workers=set();self._generation=0;self.details=None
        self._last_saved_fingerprint=None;self._last_saved_id=None;self._visible_rows=[]
        self._table_specs={};self.is_preview=bool(getattr(service,'is_preview',False))
        self.ui.previewBanner.setVisible(self.is_preview);self.ui.previewLoginNote.setVisible(self.is_preview)
        self.ui.accountLabel.setTextFormat(Qt.TextFormat.PlainText)
        self.ui.usernameEdit.setMaxLength(50);self.ui.passwordEdit.setMaxLength(1024)
        for edit,asset,position in (
            (self.ui.usernameEdit,'input-user.png',self.ui.usernameEdit.ActionPosition.LeadingPosition),
            (self.ui.passwordEdit,'input-lock.png',self.ui.passwordEdit.ActionPosition.LeadingPosition),
            (self.ui.globalSearchEdit,'search.png',self.ui.globalSearchEdit.ActionPosition.TrailingPosition),
            (self.ui.idFilterEdit,'search.png',self.ui.idFilterEdit.ActionPosition.TrailingPosition)):
            edit.addAction(QIcon(str(UI_DIR/'assets'/asset)),position)
        self.distribution=DonutChart();self.activity_chart=ActivityLineChart();self.bar_chart=TypeBarChart()
        self.success_chart=DonutChart(True);self.fail_chart=DonutChart(True)
        for host,chart in ((self.ui.distributionHost,self.distribution),(self.ui.activityHost,self.activity_chart),
                (self.ui.typeChartHost,self.bar_chart),(self.ui.successConfidenceHost,self.success_chart),
                (self.ui.failConfidenceHost,self.fail_chart)):
            while host.layout().count():
                item=host.layout().takeAt(0)
                if item.widget():item.widget().hide();item.widget().deleteLater()
            host.layout().setContentsMargins(0,0,0,0);host.layout().addWidget(chart)
        self.forms={prefix:{name:getattr(self.ui,prefix+'_'+name) for name in FIELD_MAP} for prefix in ('success','fail')}
        self.column_alignments=(Qt.AlignmentFlag.AlignLeft,Qt.AlignmentFlag.AlignLeft,Qt.AlignmentFlag.AlignRight,
            Qt.AlignmentFlag.AlignHCenter,Qt.AlignmentFlag.AlignHCenter,Qt.AlignmentFlag.AlignLeft,
            Qt.AlignmentFlag.AlignHCenter,Qt.AlignmentFlag.AlignHCenter)
        self._setup_table(self.ui.recordsTable,(90,88,115,88,110,132,148,90),(.1,.09,.14,.1,.13,.17,.18,.09),44)
        self._setup_table(self.ui.recentTable,(90,85,110,85,105,120,140),(.11,.10,.15,.11,.15,.17,.21),36)
        self.ui.recentTable.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.ui.loginButton.clicked.connect(self.login);self.ui.passwordEdit.returnPressed.connect(self.login)
        self.ui.usernameEdit.returnPressed.connect(self.ui.passwordEdit.setFocus)
        self.ui.logoutButton.clicked.connect(self.logout)
        self.ui.dashboardButton.clicked.connect(lambda:self.navigate(0))
        self.ui.lookupButton.clicked.connect(lambda:self.navigate(1))
        self.ui.recordsButton.clicked.connect(lambda:self.navigate(3))
        self.ui.quickLookupButton.clicked.connect(lambda:self.navigate(1))
        self.ui.emptyLookupButton.clicked.connect(lambda:self.navigate(1))
        self.ui.viewAllButton.clicked.connect(lambda:self.navigate(3))
        self.ui.globalSearchEdit.returnPressed.connect(self.global_search)
        for prefix,fields in self.forms.items():
            getattr(self.ui,prefix+'SubmitButton').clicked.connect(lambda checked=False,p=prefix:self.submit(p))
            getattr(self.ui,prefix+'ClearButton').clicked.connect(self.clear_forms)
            for field in fields.values():
                if isinstance(field,QComboBox):field.activated.connect(self.form_edited)
                else:field.textEdited.connect(self.form_edited)
        self.ui.idFilterEdit.textChanged.connect(self.render_records)
        for combo in (self.ui.typeFilter,self.ui.predictionFilter,self.ui.userFilter,self.ui.sortFilter):
            combo.currentIndexChanged.connect(self.render_records)
        self.ui.resetFiltersButton.clicked.connect(self.reset_filters)
        self.ui.recordsTable.cellDoubleClicked.connect(self.open_selected_record)
        self.ui.recentTable.cellDoubleClicked.connect(self.open_recent_record)
        self.clear_forms();self._clear_data();self.ui.rootStack.setCurrentIndex(0)

    def _setup_table(self,table,minimums,weights,header_height):
        self._table_specs[table]=(minimums,weights)
        table.verticalHeader().hide();table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        table.horizontalHeader().setSectionsMovable(False);table.horizontalHeader().setFixedHeight(header_height)
        table.setWordWrap(False);table.setTextElideMode(Qt.TextElideMode.ElideRight)
        for index in range(table.columnCount()):
            table.horizontalHeaderItem(index).setTextAlignment(self.column_alignments[index]|Qt.AlignmentFlag.AlignVCenter)
        table.viewport().installEventFilter(self);self._fit_table(table)

    def _fit_table(self,table):
        minimums,weights=self._table_specs[table];available=max(table.viewport().width(),sum(minimums))
        extra=available-sum(minimums);widths=[minimum+int(extra*weight) for minimum,weight in zip(minimums,weights)]
        widths[-1]+=available-sum(widths)
        for index,width in enumerate(widths):table.setColumnWidth(index,width)

    def eventFilter(self,watched,event):
        if event.type()==QEvent.Type.Resize:
            for table in getattr(self,'_table_specs',{}):
                if watched is table.viewport():self._fit_table(table)
        return super().eventFilter(watched,event)

    def _set_busy(self,busy):
        self._busy=busy
        names=('loginButton','usernameEdit','passwordEdit','logoutButton','dashboardButton','lookupButton','recordsButton',
            'quickLookupButton','emptyLookupButton','viewAllButton','successSubmitButton','failSubmitButton',
            'successClearButton','failClearButton','globalSearchEdit','idFilterEdit','typeFilter',
            'predictionFilter','userFilter','sortFilter','resetFiltersButton','recordsTable','recentTable')
        for name in names:getattr(self.ui,name).setEnabled(not busy)
        for fields in self.forms.values():
            for field in fields.values():field.setEnabled(not busy)
        if self.details:self.details.set_busy(busy)
        self.setCursor(Qt.CursorShape.WaitCursor if busy else Qt.CursorShape.ArrowCursor)

    def _run(self,function,callback,on_error=None,login_error=False):
        if self._busy:return
        generation=self._generation;self._set_busy(True)
        worker=TaskWorker(function,self);self._workers.add(worker)
        def completed(result):
            self._set_busy(False)
            if generation==self._generation:callback(result)
        def failed(message):
            self._set_busy(False)
            if generation!=self._generation:return
            if on_error:on_error(message)
            if login_error:self.show_login_error(message)
            else:QMessageBox.warning(self.details or self,'Không thể hoàn thành',message)
        def finished():self._workers.discard(worker);worker.deleteLater()
        worker.completed.connect(completed);worker.failed.connect(failed);worker.finished.connect(finished);worker.start()

    def show_login_error(self,message):
        box=QMessageBox(self);box.setWindowTitle('Đăng nhập không thành công')
        box.setIcon(QMessageBox.Icon.Warning);box.setTextFormat(Qt.TextFormat.PlainText);box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        if hasattr(QMessageBox,'Option'):box.setOption(QMessageBox.Option.DontUseNativeDialog,True)
        box.setStyleSheet('QMessageBox{background:#111111;} QLabel{color:#FFFFFF;background:transparent;font-size:14px;} QPushButton{background:#E3F398;color:#17211B;border:none;border-radius:6px;padding:9px 28px;min-width:65px;} QPushButton:hover{background:#D5EA81;}')
        box.exec()

    def login(self):
        if self._busy:return
        username=self.ui.usernameEdit.text().strip();password=self.ui.passwordEdit.text()
        if not username or not password:self.show_login_error('Vui lòng nhập tên đăng nhập và mật khẩu.');return
        self._clear_data();self.ui.passwordEdit.clear()
        self._run(lambda:self.service.authenticate(username,password),self._logged_in,login_error=True)

    def _logged_in(self,data):
        self.user=data['user'];self.ui.accountLabel.setText('●  '+user_display_name(self.user))
        self._apply_data(data);self.ui.rootStack.setCurrentIndex(1);self._show_page(0)

    def start_preview(self,show_login=False):
        if not self.is_preview:raise RuntimeError('Preview is available only with PreviewService.')
        if not show_login:self._logged_in(self.service.authenticate('preview','preview'))

    def _show_page(self,index):
        self.ui.pageStack.setCurrentIndex(index);active=0 if index==0 else 2 if index==3 else 1
        for i,button in enumerate((self.ui.dashboardButton,self.ui.lookupButton,self.ui.recordsButton)):button.setChecked(i==active)

    def navigate(self,index):
        if self._busy or not self.user:return
        self._show_page(index);user_id=self.user['user_id']
        if index==0:
            self._clear_dashboard('Đang tải thống kê…')
            self._run(lambda:self.service.load_transactions(user_id),self._apply_data,self._dashboard_error)
        elif index==3:
            self._clear_history('Đang tải lịch sử dự đoán…')
            self._run(lambda:self.service.load_history(user_id),self._apply_history,self._history_error)

    def _clear_data(self):
        self._clear_dashboard();self._users=[]
        self.ui.userFilter.blockSignals(True);self.ui.userFilter.clear();self.ui.userFilter.addItem('Tất cả người dùng',None);self.ui.userFilter.blockSignals(False)
        self._clear_history()

    def _clear_dashboard(self,message='Kiểm tra giao dịch đầu tiên để xem thống kê và biểu đồ của bạn.'):
        self._apply_data(dict(rows=[],summary=summarize([])));self.ui.emptyMessage.setText(message)

    def _dashboard_error(self,message):
        self.ui.dashboardNote.setText('Không thể tải dữ liệu giao dịch.')
        self.ui.emptyMessage.setText('Không thể tải thống kê. Mở lại Tổng quan để thử lại.')
        for label in (self.ui.totalValue,self.ui.fraudValue,self.ui.legitimateValue,self.ui.fraudRateValue):label.setText('—')

    def _clear_history(self,message='Chưa có lịch sử dự đoán.'):
        self.history_rows=[];self.render_records(empty_message=message)

    def _history_error(self,message):self._clear_history('Không thể tải lịch sử. Mở lại trang để thử lại.')

    def _apply_data(self,data):
        if data.get('rows') is None:
            self._clear_dashboard('Chưa tải lại được dữ liệu. Mở lại Tổng quan để thử lại.');return
        self.rows=list(data['rows']);summary=data['summary']
        values=(str(summary['total']),str(summary['fraud']),str(summary['legitimate']),f"{summary['fraud_rate']:.1f}%" if summary['total'] else '0%')
        for label,value in zip((self.ui.totalValue,self.ui.fraudValue,self.ui.legitimateValue,self.ui.fraudRateValue),values):label.setText(value)
        self.distribution.set_counts(summary['fraud'],summary['legitimate']);self.bar_chart.set_counts(summary['counts'])
        activity=summary.get('activity',[]);self.activity_chart.set_data(activity)
        period=''
        if activity:
            first=datetime.fromisoformat(activity[0]['date']).strftime('%d/%m/%Y')
            last=datetime.fromisoformat(activity[-1]['date']).strftime('%d/%m/%Y')
            period=first if first==last else first+' — '+last
        self.ui.activityPeriod.setText(period)
        self.ui.distributionLegend.setText(f'<span style="color:#D84A59">●</span> Fraud: {summary["fraud"]} &nbsp; <span style="color:#279E87">●</span> Legitimate: {summary["legitimate"]}')
        self.ui.fraudTypeLegend.setText(f'Tổng: {summary["fraud"]} giao dịch Fraud')
        for card in (self.ui.distributionCard,self.ui.activityCard,self.ui.typeChartCard,self.ui.recentSection):card.setVisible(bool(self.rows))
        self.ui.emptyStatePanel.setVisible(not self.rows)
        self.ui.dashboardNote.setText('Kết quả kiểm tra giao dịch của tài khoản đang đăng nhập')
        recent=sorted(self.rows,key=lambda row:(str(row.get('created_at') or ''),int(row['transaction_id'])),reverse=True)[:5]
        self._recent_rows=recent;self._populate_table(self.ui.recentTable,recent,False,'Chưa có giao dịch.')
        self.ui.recentTable.setFixedHeight(36+34*max(1,len(recent))+2)

    def _apply_history(self,data):
        self.history_rows=list(data['rows']);self._users=list(data.get('users',[]))
        selected=self.ui.userFilter.currentData();combo=self.ui.userFilter;combo.blockSignals(True)
        combo.clear();combo.addItem('Tất cả người dùng',None)
        names=[user_display_name(user) for user in self._users]
        for user in sorted(self._users,key=lambda user:(user_display_name(user).casefold(),int(user['user_id']))):
            name=user_display_name(user)
            if names.count(name)>1:name+=' ('+str(user['username'])+')'
            combo.addItem(name,int(user['user_id']))
        index=combo.findData(selected);combo.setCurrentIndex(max(0,index));combo.blockSignals(False)
        self.render_records()

    def global_search(self):
        if self._busy or not self.user:return
        query=self.ui.globalSearchEdit.text().strip();self.reset_filters()
        self.ui.idFilterEdit.setText(query);self.navigate(3)

    def reset_filters(self):
        self.ui.idFilterEdit.clear()
        for combo in (self.ui.typeFilter,self.ui.predictionFilter,self.ui.userFilter,self.ui.sortFilter):combo.setCurrentIndex(0)
        self.render_records()

    def render_records(self,*_,empty_message=None):
        query=self.ui.idFilterEdit.text().strip().casefold();selected_user=self.ui.userFilter.currentData();rows=[]
        for row in self.history_rows:
            if query and query not in str(row['transaction_id']).casefold():continue
            if self.ui.typeFilter.currentIndex()!=0 and row['type']!=self.ui.typeFilter.currentText():continue
            if self.ui.predictionFilter.currentIndex()!=0 and row['prediction']!=self.ui.predictionFilter.currentText():continue
            if selected_user is not None and str(row['user_id'])!=str(selected_user):continue
            rows.append(row)
        rows.sort(key=lambda row:(str(row.get('created_at') or ''),int(row['transaction_id'])),reverse=self.ui.sortFilter.currentIndex()==0)
        self._visible_rows=rows
        message=empty_message or ('Chưa có lịch sử dự đoán.' if not self.history_rows else 'Không có giao dịch phù hợp với bộ lọc.')
        self._populate_table(self.ui.recordsTable,rows,True,message)
        self.ui.historyCount.setText(f'{len(rows)} / {len(self.history_rows)} giao dịch')
        self.ui.userFilter.setToolTip(self.ui.userFilter.currentText())

    def _populate_table(self,table,rows,actions,empty_message):
        table.clearSpans();table.clearContents();table.setRowCount(len(rows))
        for i,row in enumerate(rows):
            table.setRowHeight(i,44 if actions else 34)
            checked_by=row.get('checked_by') or (user_display_name(self.user) if self.user and str(row['user_id'])==str(self.user['user_id']) else 'User #'+str(row['user_id']))
            values=(str(row['transaction_id']),row['type'],money_text(row['amount']),score_text(row['fraud_score']),row['prediction'],checked_by,date_text(row.get('created_at')))
            for column,value in enumerate(values):
                item=QTableWidgetItem(str(value));item.setToolTip(str(value));item.setTextAlignment(self.column_alignments[column]|Qt.AlignmentFlag.AlignVCenter)
                table.setItem(i,column,item)
            host=QWidget();layout=QHBoxLayout(host);layout.setContentsMargins(3,2,3,2);layout.setSpacing(0)
            positive=row['prediction']=='Fraud';color,fill=('#C64050','#FFF0F1') if positive else ('#208873','#E7F4ED')
            chip=QLabel(row['prediction']);chip.setTextFormat(Qt.TextFormat.PlainText);chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chip.setSizePolicy(QSizePolicy.Policy.Fixed,QSizePolicy.Policy.Preferred)
            chip.setStyleSheet(f'color:{color};background:{fill};border-radius:5px;padding:4px 7px;font-size:10px;')
            layout.addStretch();layout.addWidget(chip);layout.addStretch();table.setCellWidget(i,4,host)
            if actions:
                host=QWidget();layout=QHBoxLayout(host);layout.setContentsMargins(5,5,5,5)
                button=QPushButton('Chi tiết ↗');button.setCursor(Qt.CursorShape.PointingHandCursor);button.setFixedHeight(30)
                button.setStyleSheet('background:#F6FAF5;color:#287E69;border:1px solid #E0EBDF;border-radius:6px;padding:5px;font-size:10px;')
                button.clicked.connect(lambda checked=False,id=row['transaction_id']:self.open_record(id,True));layout.addWidget(button)
                table.setCellWidget(i,7,host)
        if not rows:
            table.setRowCount(1);table.setSpan(0,0,1,table.columnCount());table.setRowHeight(0,54)
            item=QTableWidgetItem(empty_message);item.setTextAlignment(Qt.AlignmentFlag.AlignCenter);table.setItem(0,0,item)
        self._fit_table(table)

    def open_selected_record(self,row,column):
        if 0<=row<len(self._visible_rows):self.open_record(self._visible_rows[row]['transaction_id'],True)

    def open_recent_record(self,row,column):
        if 0<=row<len(self._recent_rows):self.open_record(self._recent_rows[row]['transaction_id'],False)

    def open_record(self,transaction_id,from_history=True):
        if self._busy or not self.user:return
        user_id=self.user['user_id']
        operation=self.service.get_history_transaction if from_history else self.service.get_transaction
        self._run(lambda:operation(user_id,transaction_id),self._show_detail)

    def _show_detail(self,row):
        self.details=TransactionDetailsExt(row,self);self.details.exec();self.details=None

    def form_edited(self,*_):
        self.ui.successResultBadge.hide();self.ui.failResultBadge.hide()
        self.success_chart.set_probability(None);self.fail_chart.set_probability(None)

    def clear_forms(self):
        for fields in self.forms.values():
            for field in fields.values():
                if isinstance(field,QComboBox):field.setCurrentIndex(-1)
                else:field.clear()
        self._last_saved_fingerprint=None;self._last_saved_id=None;self.form_edited()

    def submit(self,prefix):
        if self._busy or not self.user:return
        raw={FIELD_MAP[name]:(field.currentText() if isinstance(field,QComboBox) else field.text().strip()) for name,field in self.forms[prefix].items()}
        try:
            payload = validate_payload(raw)
        except ApplicationError as exc:
            QMessageBox.warning(
                self,
                "Dữ liệu giao dịch không hợp lệ",
                str(exc),
            )
            return
        fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()
        if fingerprint==self._last_saved_fingerprint:
            QMessageBox.information(self,'Giao dịch đã lưu',f'Giao dịch #{self._last_saved_id} đã được lưu. Chọn Clear để bắt đầu giao dịch mới.');return
        user_id=self.user['user_id']
        def saved(data):
            self._last_saved_fingerprint=fingerprint;self._last_saved_id=data['transaction_id']
            self._apply_data(data);self.show_prediction(data)
            if data.get('refresh_error'):QMessageBox.information(self,'Giao dịch đã lưu',data['refresh_error'])
        self._run(lambda:self.service.predict_and_save(user_id,payload),saved)

    def show_prediction(self,data):
        result=data['result'];success=result.prediction=='Legitimate';payload=data['payload']
        for fields in self.forms.values():
            for name,field in fields.items():
                value=str(payload[FIELD_MAP[name]])
                if isinstance(field,QComboBox):field.setCurrentText(value)
                else:field.setText(value)
        self.success_chart.set_probability(result.fraud_score,success);self.fail_chart.set_probability(result.fraud_score,success)
        self.ui.successResultText.setText('Legitimate');self.ui.failResultText.setText('Fraud')
        self.ui.successResultBadge.setVisible(success);self.ui.failResultBadge.setVisible(not success)
        badge=self.ui.successResultBadge if success else self.ui.failResultBadge
        badge.setToolTip(f'Đã lưu giao dịch #{data["transaction_id"]} · {result.prediction} · Ngưỡng {result.threshold:.16f}')
        self._show_page(1 if success else 2)

    def logout(self):
        if self._busy:return
        self._generation+=1;self.user=None;self.clear_forms();self.reset_filters();self._clear_data()
        self.ui.usernameEdit.clear();self.ui.passwordEdit.clear();self.ui.globalSearchEdit.clear();self.ui.accountLabel.clear();self.ui.rootStack.setCurrentIndex(0)

    def closeEvent(self,event):
        if any(worker.isRunning() for worker in self._workers):
            event.ignore();QMessageBox.information(self,'Đang xử lý','Vui lòng chờ thao tác đọc/ghi hoàn tất rồi đóng ứng dụng.');return
        event.accept()
