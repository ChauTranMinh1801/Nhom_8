import sys
from PyQt6.QtWidgets import QApplication,QMessageBox
from AegisService import Settings,ApplicationService
from AegisExt import AegisExt

def main():
    app=QApplication(sys.argv);app.setStyle('Fusion')
    try:service=ApplicationService(Settings.from_env())
    except Exception as exc:
        QMessageBox.critical(None,'Cấu hình AEGIS',str(exc));return 1
    window=AegisExt(service);window.show();return app.exec()

if __name__=='__main__':sys.exit(main())
