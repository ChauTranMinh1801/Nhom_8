"""Run the real app, or an explicitly separated UI preview."""
import argparse
import sys
from PyQt6.QtWidgets import QApplication,QMessageBox
from AegisService import Settings,ApplicationService
from AegisExt import AegisExt

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--preview',action='store_true',help='UI mock data only; no MySQL/model access')
    parser.add_argument('--empty',action='store_true',help='Empty UI preview (requires --preview)')
    parser.add_argument('--login',action='store_true',help='Start preview at the login screen')
    args=parser.parse_args()
    if (args.empty or args.login) and not args.preview:parser.error('--empty/--login phải dùng cùng --preview')
    app=QApplication(sys.argv[:1]);app.setStyle('Fusion')
    try:
        if args.preview:
            from PreviewService import PreviewService
            service=PreviewService(empty=args.empty)
        else:service=ApplicationService(Settings.from_env())
        window=AegisExt(service)
    except Exception as exc:
        QMessageBox.critical(None,'Cấu hình AEGIS',str(exc));return 1
    screen=app.primaryScreen().availableGeometry()
    window.resize(min(1360,max(1160,screen.width()-40)),min(860,max(700,screen.height()-70)))
    if args.preview:window.start_preview(show_login=args.login)
    window.show();return app.exec()

if __name__=='__main__':sys.exit(main())
