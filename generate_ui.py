"""Generate UI-only Python classes; interactions remain in AegisExt.py."""
from pathlib import Path
from PyQt6 import uic
root=Path(__file__).resolve().parent
for source,target in (('Aegis.ui','Ui_Aegis.py'),('TransactionDetails.ui','Ui_TransactionDetails.py')):
    with (root/'ui'/source).open('r',encoding='utf-8') as ui_file, (root/'ui'/target).open('w',encoding='utf-8',newline='\n') as output:
        uic.compileUi(ui_file,output)
    print('Generated ui/'+target)
