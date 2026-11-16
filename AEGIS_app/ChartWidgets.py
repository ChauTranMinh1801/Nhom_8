"""PyQt6 chart rendering only; data is supplied by Ext/services."""
import math
from PyQt6.QtCore import Qt,QRectF,QPointF
from PyQt6.QtGui import QColor,QFont,QPainter,QPen,QPainterPath
from PyQt6.QtWidgets import QWidget,QToolTip,QSizePolicy

TEAL='#279E87';FRAUD='#D84A59';TEXT='#234236';MUTED='#819087';GRID='#EAF0E9'
TYPE_ORDER=('CASH_IN','CASH_OUT','DEBIT','PAYMENT','TRANSFER')


def empty_message(painter,rect,message='Chưa có dữ liệu'):
    painter.setPen(QColor(MUTED));painter.setFont(QFont('Arial',10))
    painter.drawText(rect,Qt.AlignmentFlag.AlignCenter,message)

class DonutChart(QWidget):
    def __init__(self,probability_mode=False,parent=None):
        super().__init__(parent)
        self.probability_mode=probability_mode;self.value=None
        self.positive=0;self.negative=0;self.success=True
        self.setMinimumSize(160,175);self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)

    def set_counts(self,positive,negative):
        self.positive=int(positive);self.negative=int(negative)
        total=self.positive+self.negative
        self.value=self.positive/total if total else None
        self.setToolTip(f'Fraud: {self.positive} · Legitimate: {self.negative}')
        self.update()

    def set_probability(self,value,success=True):
        self.value=None if value is None else max(0.,min(1.,float(value)))
        self.success=success
        self.setToolTip('Chưa có kết quả' if self.value is None else f'Điểm Fraud: {self.value*100:.6f}%')
        self.update()

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.value is None and not self.probability_mode:
            empty_message(p,self.rect());p.end();return
        s=max(20,min(self.width()-24,self.height()-18,218));cx,cy=self.width()/2,self.height()/2
        rect=QRectF(cx-s/2,cy-s/2,s,s)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#E9EEEA' if self.probability_mode else TEAL));p.drawEllipse(rect)
        if self.value is not None:
            color=FRAUD if not self.probability_mode or not self.success else TEAL
            p.setBrush(QColor(color));p.drawPie(rect,90*16,-round(self.value*360*16))
        inner=rect.adjusted(s*.235,s*.235,-s*.235,-s*.235)
        p.setBrush(QColor('white'));p.drawEllipse(inner)
        if self.value is None:center='—'
        elif self.probability_mode:center=f'{self.value*100:.3f}'.rstrip('0').rstrip('.')+'%'
        else:center=f'{self.value*100:.1f}%'
        size=23;p.setFont(QFont('Arial',size,QFont.Weight.Bold))
        while p.fontMetrics().horizontalAdvance(center)>inner.width()-10 and size>11:
            size-=1;p.setFont(QFont('Arial',size,QFont.Weight.Bold))
        color=FRAUD if self.probability_mode and not self.success else TEXT
        p.setPen(QColor(color));p.drawText(inner,Qt.AlignmentFlag.AlignCenter,center)
        # Intentionally no percentage labels around the confidence ring.
        p.end()

class TypeBarChart(QWidget):
    """One Fraud count per type; no combined Fraud/Legitimate series."""
    def __init__(self,parent=None):
        super().__init__(parent);self.counts={};self.setMinimumSize(240,175)

    def set_counts(self,counts):
        self.counts={kind:int(counts.get(kind,(0,0))[0]) if isinstance(counts.get(kind,(0,0)),(list,tuple)) else int(counts.get(kind,0)) for kind in TYPE_ORDER}
        self.setToolTip('\n'.join(f'{kind}: {count} Fraud' for kind,count in self.counts.items()))
        self.update()

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.counts:empty_message(p,self.rect());p.end();return
        p.setFont(QFont('Arial',8));left,top,right,bottom=30,18,self.width()-8,self.height()-32
        peak=max(self.counts.values(),default=0);tick_step=max(1,math.ceil(peak/4));ceiling=4*tick_step
        for i in range(5):
            y=bottom-(bottom-top)*i/4
            p.setPen(QColor(GRID));p.drawLine(QPointF(left,y),QPointF(right,y))
            p.setPen(QColor(MUTED));p.drawText(QRectF(0,y-8,left-6,18),Qt.AlignmentFlag.AlignRight,str(i*tick_step))
        step=(right-left)/len(TYPE_ORDER);width=min(34,step*.57)
        for i,kind in enumerate(TYPE_ORDER):
            value=self.counts[kind];x=left+step*(i+.5);height=(bottom-top)*value/ceiling
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(FRAUD))
            if value:p.drawRoundedRect(QRectF(x-width/2,bottom-height,width,height),4,4)
            p.setPen(QColor(TEXT));p.drawText(QRectF(x-step/2,bottom-height-20,step,18),Qt.AlignmentFlag.AlignCenter,str(value))
            p.setPen(QColor(MUTED));p.drawText(QRectF(x-step/2,bottom+10,step,20),Qt.AlignmentFlag.AlignCenter,kind)
        p.end()

class ActivityLineChart(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.activity=[];self.points=[]
        self.setMinimumSize(210,175);self.setMouseTracking(True)

    def set_data(self,activity):
        self.activity=[dict(item) for item in activity];self.points=[];self.update()

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.activity:empty_message(p,self.rect(),'Chưa có dữ liệu thời gian');p.end();return
        left,top,right,bottom=30,18,self.width()-10,self.height()-32
        peak=max(item['count'] for item in self.activity);tick_step=max(1,math.ceil(peak/4));ceiling=4*tick_step
        p.setFont(QFont('Arial',8))
        for i in range(5):
            y=bottom-(bottom-top)*i/4
            p.setPen(QColor(GRID));p.drawLine(QPointF(left,y),QPointF(right,y))
            p.setPen(QColor(MUTED));p.drawText(QRectF(0,y-8,left-6,18),Qt.AlignmentFlag.AlignRight,str(i*tick_step))
        count=len(self.activity)
        self.points=[QPointF(left+(right-left)*i/max(1,count-1),bottom-(bottom-top)*item['count']/ceiling) for i,item in enumerate(self.activity)]
        if count==1:self.points=[QPointF((left+right)/2,self.points[0].y())]
        path=QPainterPath(self.points[0])
        for point in self.points[1:]:path.lineTo(point)
        area=QPainterPath(path);area.lineTo(self.points[-1].x(),bottom);area.lineTo(self.points[0].x(),bottom);area.closeSubpath()
        fill=QColor(TEAL);fill.setAlpha(22);p.fillPath(area,fill)
        p.setPen(QPen(QColor(TEAL),2.5));p.drawPath(path)
        for point in self.points:
            p.setBrush(QColor('white'));p.setPen(QPen(QColor(TEAL),1.8));p.drawEllipse(point,3.2,3.2)
        indices=sorted(set((0,count//2,count-1)))
        p.setPen(QColor(MUTED))
        for i in indices:
            x=self.points[i].x();text=self.activity[i]['label']
            alignment=Qt.AlignmentFlag.AlignLeft if i==0 and count>1 else Qt.AlignmentFlag.AlignRight if i==count-1 and count>1 else Qt.AlignmentFlag.AlignCenter
            rect=QRectF(x if i==0 else x-45,bottom+10,45 if i in (0,count-1) and count>1 else 90,20)
            if i==count-1 and count>1:rect=QRectF(x-45,bottom+10,45,20)
            if count==1:rect=QRectF(x-45,bottom+10,90,20)
            p.drawText(rect,alignment,text)
        p.end()

    def mouseMoveEvent(self,event):
        if not self.points:return
        index=min(range(len(self.points)),key=lambda i:abs(self.points[i].x()-event.position().x()))
        point=self.points[index]
        if abs(point.x()-event.position().x())<14:
            item=self.activity[index]
            QToolTip.showText(event.globalPosition().toPoint(),f'{item["date"]}: {item["count"]} giao dịch',self)
        else:QToolTip.hideText()
        super().mouseMoveEvent(event)
