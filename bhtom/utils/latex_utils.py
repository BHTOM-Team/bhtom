from typing import Any, List
from pylatex import Document
from pylatex.table import Tabularx


def data_to_latex_table(data: List[List[Any]], columns: List[str], filename: str) -> str:
    doc: Document = Document(filename)

    with doc.create(Tabularx("lX lX l", width=3)) as table:
        table.add_hline()
        table.add_row([col.replace('_', ' ') for col in columns])
        table.add_hline()
        table.add_hline()

        for datum in data:
            table.add_row(datum)

        table.add_hline()
        table.add_hline()

    return doc.dumps()
