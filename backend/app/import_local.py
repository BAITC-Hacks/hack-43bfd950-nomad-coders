"""Local archive loader. Source files and workbooks never enter the Git tree."""
import argparse
import time
import zipfile
from datetime import date
from pathlib import PurePosixPath

from app.config import Settings
from app.contracts import CalculationRequest, CalculationSettings
from app.ingestion import SourceWorkbook
from app.service import Service


def read_archive(path):
    files=[]
    with zipfile.ZipFile(path) as archive:
        entries=[i for i in archive.infolist() if i.filename.lower().endswith('.xlsx') and not i.is_dir()]
        if sum(i.file_size for i in entries)>30*1024*1024:
            raise ValueError('Сумма книг в архиве превышает 30 МиБ')
        for entry in entries:
            name=entry.filename
            if not entry.flag_bits & 0x800:
                try:
                    name=name.encode('cp437').decode('cp866')
                except (UnicodeEncodeError,UnicodeDecodeError):
                    pass
            files.append(SourceWorkbook(PurePosixPath(name.replace('\\','/')).name,archive.read(entry)))
    return files


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Импорт известных XLSX из локального ZIP')
    parser.add_argument('--supplier',choices=['systeme','iek'],required=True)
    parser.add_argument('--archive',required=True)
    parser.add_argument('--as-of',type=date.fromisoformat,help='После импорта рассчитать на эту дату (ISO)')
    args=parser.parse_args()
    service=Service(Settings.from_env())
    started=time.perf_counter()
    dataset=service.import_dataset(read_archive(args.archive),args.supplier)
    print(f'Набор: {dataset.id}; проблем импорта: {len(dataset.issues)}; время: {time.perf_counter()-started:.1f} с')
    if args.as_of:
        started=time.perf_counter()
        result=service.calculate(CalculationRequest(dataset_id=dataset.id,settings=CalculationSettings(as_of=args.as_of)))
        counts={state:sum(r.urgency==state for r in result.recommendations) for state in ['order_now','expedite','covered','needs_input']}
        print(f'Расчёт: {result.id}; время: {time.perf_counter()-started:.1f} с; {counts}')
