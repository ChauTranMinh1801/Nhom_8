"""Presentation widgets only. Counts/probabilities are supplied by Ext."""
from PyQt6.QtCore import Qt,QRectF
from PyQt6.QtGui import QColor,QFont,QPainter
from PyQt6.QtWidgets import QWidget

TEAL,LIME,GREEN,RED = '#00595C','#E3F398','#279E87','#C80D12'

class DonutChart(QWidget):
    def __init__(self,probability_mode=False,parent=None):
        super().__init__(parent)
        self.probability_mode = probability_mode
        self.value = None
        self.positive = 0
        self.negative = 0
        self.success = True
        self.setMinimumSize(230,240)

    def set_counts(self,positive,negative):
        self.positive,self.negative = positive,negative
        self.value = positive/(positive+negative) if positive+negative else None
        self.update()

    def set_probability(self,value,success=True):
        self.value,self.success = value,success
        self.update()

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s=min(self.width()-55,self.height()-60,215);cx,cy=self.width()/2,self.height()/2
        rect=QRectF(cx-s/2,cy-s/2,s,s)
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#E9E8E5' if self.probability_mode else LIME));p.drawEllipse(rect)
        if self.value is not None:
            p.setBrush(QColor(TEAL));p.drawPie(rect,90*16,-round(self.value*360*16))
        inner=rect.adjusted(s*.25,s*.25,-s*.25,-s*.25)
        p.setBrush(QColor('white'));p.drawEllipse(inner)
        color = GREEN if self.probability_mode and self.success else RED if self.probability_mode else TEAL
        p.setPen(QColor(color))
        if self.value is None:
            center_text='—'
        elif self.probability_mode:
            center_text=f'{self.value*100:.3f}'.rstrip('0').rstrip('.')+'%'
        else:
            center_text=f'{self.value*100:.1f}%'
        point_size=23
        p.setFont(QFont('Arial',point_size,QFont.Weight.Bold))
        while p.fontMetrics().horizontalAdvance(center_text)>inner.width()-8 and point_size>12:
            point_size-=1;p.setFont(QFont('Arial',point_size,QFont.Weight.Bold))
        p.drawText(inner,Qt.AlignmentFlag.AlignCenter,center_text)
        if self.probability_mode and self.value is not None:
            p.setPen(QColor('#555555'));p.setFont(QFont('Arial',8))
            p.drawText(QRectF(cx-40,rect.top()-22,80,18),Qt.AlignmentFlag.AlignCenter,f'{(1-self.value)*100:.3f}%' )
            p.drawText(QRectF(cx-40,rect.bottom()+4,80,18),Qt.AlignmentFlag.AlignCenter,f'{self.value*100:.3f}%' )
        p.end()

class TypeBarChart(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.counts={};self.setMinimumSize(390,265)

    def set_counts(self,counts):
        self.counts = dict(counts);self.update()

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setFont(QFont('Arial',9))
        kinds=tuple(self.counts) or ('TRANSFER','CASH_OUT','PAYMENT','CASH_IN','DEBIT')
        maximum=max([max(v) for v in self.counts.values()]+[1])
        # Use integer ticks: transactions are counts, never fractional units.
        tick_step=max(1,(maximum+3)//4);ceiling=tick_step*4
        left,top,right,bottom=40,25,self.width()-15,self.height()-42
        for i in range(5):
            y=bottom-(bottom-top)*i/4
            p.setPen(QColor('#E7ECE8'));p.drawLine(int(left),int(y),int(right),int(y))
            p.setPen(QColor('#74817A'));p.drawText(QRectF(0,y-8,left-7,18),Qt.AlignmentFlag.AlignRight,str(tick_step*i))
        step=(right-left)/len(kinds);bw=min(28,step*.3)
        for i,kind in enumerate(kinds):
            center=left+step*(i+.5)
            for j,(value,color) in enumerate(zip(self.counts.get(kind,(0,0)),(TEAL,LIME))):
                h=(bottom-top)*value/ceiling;x=center-bw-2+j*(bw+4)
                p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(color));p.drawRoundedRect(QRectF(x,bottom-h,bw,h),3,3)
                if value:
                    p.setPen(QColor('#546259'));p.drawText(QRectF(x,bottom-h-20,bw,18),Qt.AlignmentFlag.AlignCenter,str(value))
            p.setPen(QColor('#536059'));p.drawText(QRectF(center-step/2,bottom+12,step,20),Qt.AlignmentFlag.AlignCenter,kind)
        p.end()
