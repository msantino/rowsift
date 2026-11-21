"""Write the synthetic fixtures of the reading layer and the grid each one must give.

Run it from the repository root when a fixture changes:

    uv run --with xlwt python scripts/generate_reading_fixtures.py

Every fixture is built here from invented data, next to the grid it must read
as. The expected grids are written by hand, never produced by the reader.
Workbooks in XLSX are assembled from raw XML so that a formula can carry its
stored result, which a spreadsheet library cannot write.
"""

from __future__ import annotations

import datetime
import io
import json
import struct
import zipfile
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "reading"
EPOCH = datetime.date(1899, 12, 30)

# Cell kinds understood by the XLSX builder.
DATE = "date"
DATETIME = "datetime"
TIME = "time"
FORMULA = "formula"


def column_letters(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def serial(moment: datetime.date | datetime.datetime) -> float:
    if isinstance(moment, datetime.datetime):
        delta = moment - datetime.datetime(1899, 12, 30)
        return delta.days + delta.seconds / 86400
    return float((moment - EPOCH).days)


def cell_xml(reference: str, value: Any, strings: list[str]) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return f'<c r="{reference}" t="b"><v>{int(value)}</v></c>'
    if isinstance(value, str):
        if value not in strings:
            strings.append(value)
        return f'<c r="{reference}" t="s"><v>{strings.index(value)}</v></c>'
    if isinstance(value, int | float):
        return f'<c r="{reference}"><v>{value!r}</v></c>'
    kind = value[0]
    if kind == DATE:
        return f'<c r="{reference}" s="1"><v>{serial(value[1])!r}</v></c>'
    if kind == DATETIME:
        return f'<c r="{reference}" s="2"><v>{serial(value[1])!r}</v></c>'
    if kind == TIME:
        return f'<c r="{reference}" s="3"><v>{value[1]!r}</v></c>'
    if kind == FORMULA:
        formula, cached = value[1], value[2]
        return f'<c r="{reference}" t="str"><f>{escape(formula)}</f><v>{escape(cached)}</v></c>'
    raise ValueError(kind)


def sheet_xml(
    rows: list[list[Any]],
    strings: list[str],
    merges: list[str],
    dimension: str | None,
) -> str:
    body = []
    for row_index, row in enumerate(rows, start=1):
        cells = "".join(
            cell_xml(f"{column_letters(col)}{row_index}", value, strings)
            for col, value in enumerate(row)
        )
        body.append(f'<row r="{row_index}">{cells}</row>')
    merge_xml = ""
    if merges:
        items = "".join(f'<mergeCell ref="{ref}"/>' for ref in merges)
        merge_xml = f'<mergeCells count="{len(merges)}">{items}</mergeCells>'
    dim = f'<dimension ref="{dimension}"/>' if dimension else ""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"{dim}<sheetData>{''.join(body)}</sheetData>{merge_xml}</worksheet>"
    )


STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    '<fonts count="1"><font><sz val="11"/></font></fonts>'
    '<fills count="2"><fill><patternFill patternType="none"/></fill>'
    '<fill><patternFill patternType="gray125"/></fill></fills>'
    '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    '<cellXfs count="4">'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="14" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
    '<xf numFmtId="22" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
    '<xf numFmtId="21" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
    '</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
    "</styleSheet>"
)


def xlsx(
    sheets: list[tuple[str, list[list[Any]]]],
    *,
    merges: dict[str, list[str]] | None = None,
    dimensions: dict[str, str] | None = None,
) -> bytes:
    """Assemble a workbook. ``sheets`` are (name, rows) pairs."""
    merges = merges or {}
    dimensions = dimensions or {}
    strings: list[str] = []
    sheet_parts = [
        sheet_xml(rows, strings, merges.get(name, []), dimensions.get(name))
        for name, rows in sheets
    ]
    shared = "".join(f'<si><t xml:space="preserve">{escape(text)}</t></si>' for text in strings)
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{ns}" xmlns:r="{rel_ns}"><sheets>'
        + "".join(
            f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
            for i, (name, _) in enumerate(sheets, start=1)
        )
        + "</sheets></workbook>"
    )
    pkg = "http://schemas.openxmlformats.org/package/2006/relationships"
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{pkg}">'
        + "".join(
            f'<Relationship Id="rId{i}" Type="{rel_ns}/worksheet" '
            f'Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(sheets) + 1)
        )
        + f'<Relationship Id="rId{len(sheets) + 1}" Type="{rel_ns}/styles" Target="styles.xml"/>'
        + f'<Relationship Id="rId{len(sheets) + 2}" Type="{rel_ns}/sharedStrings" '
        'Target="sharedStrings.xml"/></Relationships>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{pkg}"><Relationship Id="rId1" '
        f'Type="{rel_ns}/officeDocument" Target="xl/workbook.xml"/></Relationships>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + "".join(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for i in range(1, len(sheets) + 1)
        )
        + '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        "</Types>"
    )
    parts = {
        "[Content_Types].xml": content_types,
        "_rels/.rels": root_rels,
        "xl/workbook.xml": workbook,
        "xl/_rels/workbook.xml.rels": workbook_rels,
        "xl/styles.xml": STYLES,
        "xl/sharedStrings.xml": (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><sst xmlns="{ns}" '
            f'count="{len(strings)}" uniqueCount="{len(strings)}">{shared}</sst>'
        ),
    }
    for i, part in enumerate(sheet_parts, start=1):
        parts[f"xl/worksheets/sheet{i}.xml"] = part
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in parts.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
    return buffer.getvalue()


def declare_uncompressed_size(workbook: bytes, size: int) -> bytes:
    """Rewrite the declared uncompressed size of the first central directory entry."""
    marker = workbook.index(b"PK\x01\x02")
    patched = bytearray(workbook)
    struct.pack_into("<I", patched, marker + 24, size)
    return bytes(patched)


def xls() -> dict[str, bytes]:
    import xlwt

    book = xlwt.Workbook()
    date_style = xlwt.easyxf(num_format_str="YYYY-MM-DD")
    datetime_style = xlwt.easyxf(num_format_str="YYYY-MM-DD HH:MM:SS")
    time_style = xlwt.easyxf(num_format_str="HH:MM:SS")
    people = book.add_sheet("People")
    people.write(0, 0, "Name")
    people.write(0, 1, "Phone")
    people.write(0, 2, "Joined")
    people.write(0, 3, "Seen")
    people.write(0, 4, "Active")
    people.write(0, 5, "Score")
    people.write(1, 0, "Ana Silva")
    people.write(1, 1, 11999990001.0)
    people.write(1, 2, datetime.date(2024, 3, 15), date_style)
    people.write(1, 3, datetime.datetime(2024, 3, 15, 13, 45, 30), datetime_style)
    people.write(1, 4, True)
    people.write(1, 5, 7.5)
    people.write(2, 0, "Bruno Costa")
    people.write(2, 1, 11999990002.0)
    people.write(2, 2, datetime.date(2023, 12, 1), date_style)
    people.write(2, 3, datetime.time(8, 5, 0), time_style)
    people.write(2, 4, False)
    people.write(2, 5, 3.0)
    people.write_merge(3, 5, 0, 0, "North")
    people.write(3, 1, "a")
    people.write(4, 1, "b")
    people.write(5, 1, "c")
    # An empty first sheet in front would hide the second one: keep this book simple.
    buffer = io.BytesIO()
    book.save(buffer)
    first = buffer.getvalue()

    book = xlwt.Workbook()
    book.add_sheet("Cover")
    data = book.add_sheet("Data")
    data.write(0, 0, "Name")
    data.write(1, 0, "Carla Dias")
    buffer = io.BytesIO()
    book.save(buffer)
    second_sheet = buffer.getvalue()

    book = xlwt.Workbook()
    durations = book.add_sheet("Hours")
    hours_style = xlwt.easyxf(num_format_str="[h]:mm:ss")
    durations.write(0, 0, "Worked")
    durations.write(1, 0, (37 * 3600 + 45 * 60 + 30) / 86400, hours_style)
    durations.write(2, 0, (8 * 3600 + 5 * 60) / 86400, hours_style)
    durations.write(3, 0, datetime.datetime(2024, 3, 15, 13, 45, 30), datetime_style)
    buffer = io.BytesIO()
    book.save(buffer)
    return {"types": first, "second_sheet": second_sheet, "duration": buffer.getvalue()}


def write(folder: str, name: str, content: bytes, expected: dict[str, Any]) -> None:
    target = ROOT / folder
    target.mkdir(parents=True, exist_ok=True)
    (target / name).write_bytes(content)
    stem = name.rsplit(".", 1)[0]
    (target / f"{stem}.expected.json").write_text(
        json.dumps(expected, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def text_report(
    encoding: str, delimiter: str | None, rows: list[list[str]], **extra: Any
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "format": "csv",
        "encoding": encoding,
        "delimiter": delimiter,
        "sheet": None,
        "sheets": [],
        "row_count": len(rows),
        "column_count": len(rows[0]) if rows else 0,
        "notes": [],
    }
    report.update(extra)
    return report


def csv_fixture(
    folder: str,
    name: str,
    content: bytes,
    rows: list[list[str]],
    encoding: str,
    delimiter: str | None,
    **extra: Any,
) -> None:
    write(
        folder,
        name,
        content,
        {"rows": rows, "report": text_report(encoding, delimiter, rows, **extra)},
    )


def book_report(
    fmt: str, sheet: str | None, sheets: list[str], rows: list[list[str]], notes: list[str]
) -> dict[str, Any]:
    return {
        "format": fmt,
        "encoding": None,
        "delimiter": None,
        "sheet": sheet,
        "sheets": sheets,
        "row_count": len(rows),
        "column_count": len(rows[0]) if rows else 0,
        "notes": notes,
    }


def main() -> None:
    # Encodings.
    rows = [["Nome", "Telefone"], ["Ana Silva", "11999990001"]]
    csv_fixture(
        "encoding",
        "utf8_bom.csv",
        b"\xef\xbb\xbfNome;Telefone\nAna Silva;11999990001\n",
        rows,
        "utf-8",
        ";",
        notes=["bom_removed"],
    )
    rows = [["Nome", "Cidade"], ["João", "São Paulo"]]
    csv_fixture(
        "encoding",
        "cp1252.csv",
        "Nome;Cidade\nJoão;São Paulo\n".encode("cp1252"),
        rows,
        "cp1252",
        ";",
    )
    rows = [["Nome", "Telefone"], ["Ana Silva", "11999990001"]]
    csv_fixture(
        "encoding",
        "utf16le_tab.txt",
        b"\xff\xfe" + "Nome\tTelefone\r\nAna Silva\t11999990001\r\n".encode("utf-16-le"),
        rows,
        "utf-16-le",
        "\t",
        notes=["bom_removed"],
    )
    csv_fixture(
        "encoding",
        "utf16be_no_mark.txt",
        "Nome\tTelefone\r\nAna Silva\t11999990001\r\n".encode("utf-16-be"),
        rows,
        "utf-16-be",
        "\t",
    )
    csv_fixture(
        "encoding",
        "utf8_plain.csv",
        "Nome,Cidade\nJoão,São Paulo\n".encode(),
        [["Nome", "Cidade"], ["João", "São Paulo"]],
        "utf-8",
        ",",
    )
    csv_fixture(
        "encoding",
        "latin1_undefined_in_cp1252.csv",
        b"Code;Name\nA\x81;Jo\xe3o\n",
        [["Code", "Name"], ["A\x81", "João"]],
        "latin-1",
        ";",
    )

    # Delimiters and quoting.
    csv_fixture(
        "delimiter",
        "semicolon_quoted_commas.csv",
        b'"Silva, Ana";11999990001\n"Costa, Bruno";11999990002\n',
        [["Silva, Ana", "11999990001"], ["Costa, Bruno", "11999990002"]],
        "utf-8",
        ";",
    )
    csv_fixture(
        "delimiter",
        "single_column.csv",
        b"11999990001\n11999990002\n11999990003\n",
        [["11999990001"], ["11999990002"], ["11999990003"]],
        "utf-8",
        None,
    )
    csv_fixture(
        "delimiter",
        "pipe.csv",
        b"Nome|Cidade|UF\nAna|Recife|PE\nBruno|Natal|RN\n",
        [["Nome", "Cidade", "UF"], ["Ana", "Recife", "PE"], ["Bruno", "Natal", "RN"]],
        "utf-8",
        "|",
    )
    csv_fixture(
        "delimiter",
        "comma_in_free_text_of_semicolon_file.csv",
        b"Nome;Endereco;Cidade\nAna;Rua A, 10;Recife\nBruno;Rua B, 20;Natal\n",
        [
            ["Nome", "Endereco", "Cidade"],
            ["Ana", "Rua A, 10", "Recife"],
            ["Bruno", "Rua B, 20", "Natal"],
        ],
        "utf-8",
        ";",
    )
    csv_fixture(
        "delimiter",
        "quoted_newline_and_quote.csv",
        b'Nome,Nota\nAna,"linha um\nlinha dois"\nBruno,"disse ""oi"""\n',
        [["Nome", "Nota"], ["Ana", "linha um\nlinha dois"], ["Bruno", 'disse "oi"']],
        "utf-8",
        ",",
    )
    csv_fixture(
        "delimiter",
        "unterminated_quote.csv",
        b'name\n"abc\nrow2\nrow3\n',
        [["name"], ["abc\nrow2\nrow3\n"]],
        "utf-8",
        None,
        notes=["unterminated_quote"],
    )
    csv_fixture(
        "delimiter",
        "crlf_and_cr_line_ends.csv",
        b"a,b\r\n1,2\r\n3,4\r5,6\r",
        [["a", "b"], ["1", "2"], ["3", "4"], ["5", "6"]],
        "utf-8",
        ",",
    )

    # Grid shape.
    csv_fixture(
        "grid",
        "ragged_rows.csv",
        b"a,b,c\n1,2\n3,4,5,6\n",
        [["a", "b", "c", ""], ["1", "2", "", ""], ["3", "4", "5", "6"]],
        "utf-8",
        ",",
    )
    csv_fixture(
        "grid",
        "trailing_empty_columns.csv",
        b"a;b;;\n1;2;;\n3;4;;\n",
        [["a", "b"], ["1", "2"], ["3", "4"]],
        "utf-8",
        ";",
        notes=["trailing_empty_columns_dropped"],
    )
    csv_fixture("grid", "empty_file.csv", b"", [], "utf-8", None)

    # Workbook cells.
    types_rows = [
        ["Name", "Phone", "Joined", "Seen", "Active", "Score", "Full name"],
        [
            "Ana",
            11999990001.0,
            (DATE, datetime.date(2024, 3, 15)),
            (DATETIME, datetime.datetime(2024, 3, 15, 13, 45, 30)),
            True,
            7.5,
            (FORMULA, 'A2&" "&"Silva"', "Ana Silva"),
        ],
        [
            "Bruno",
            11999990002,
            (DATE, datetime.date(2023, 12, 1)),
            (TIME, 8 * 3600 / 86400),
            False,
            3.0,
            (FORMULA, 'A3&" "&"Costa"', "Bruno Costa"),
        ],
    ]
    types_expected = [
        ["Name", "Phone", "Joined", "Seen", "Active", "Score", "Full name"],
        ["Ana", "11999990001", "2024-03-15", "2024-03-15T13:45:30", "true", "7.5", "Ana Silva"],
        ["Bruno", "11999990002", "2023-12-01", "08:00:00", "false", "3", "Bruno Costa"],
    ]
    write(
        "workbook_cells",
        "types.xlsx",
        xlsx([("People", types_rows)]),
        {
            "rows": types_expected,
            "report": book_report("xlsx", "People", ["People"], types_expected, []),
        },
    )
    xls_books = xls()
    xls_expected = [
        ["Name", "Phone", "Joined", "Seen", "Active", "Score"],
        ["Ana Silva", "11999990001", "2024-03-15", "2024-03-15T13:45:30", "true", "7.5"],
        ["Bruno Costa", "11999990002", "2023-12-01", "08:05:00", "false", "3"],
        ["North", "a", "", "", "", ""],
        ["North", "b", "", "", "", ""],
        ["North", "c", "", "", "", ""],
    ]
    write(
        "workbook_cells",
        "types_legacy.xls",
        xls_books["types"],
        {
            "rows": xls_expected,
            "report": book_report(
                "xls", "People", ["People"], xls_expected, ["merged_cells_filled"]
            ),
        },
    )
    phone_rows = [["Phone"], [11999990001.0]]
    write(
        "workbook_cells",
        "phone_as_number.xlsx",
        xlsx([("Sheet1", phone_rows)]),
        {
            "rows": [["Phone"], ["11999990001"]],
            "report": book_report("xlsx", "Sheet1", ["Sheet1"], [["Phone"], ["x"]], []),
            "read_args": {"filename": "list.csv"},
        },
    )
    trailing = [["a", "b"], ["1", "2"], [], []]
    write(
        "workbook_cells",
        "huge_dimension_small_data.xlsx",
        xlsx([("Sheet1", trailing)], dimensions={"Sheet1": "A1:XFD1048576"}),
        {
            "rows": [["a", "b"], ["1", "2"]],
            "report": book_report(
                "xlsx",
                "Sheet1",
                ["Sheet1"],
                [["a", "b"], ["1", "2"]],
                [],
            ),
        },
    )
    write(
        "workbook_cells",
        "wrong_dimension.xlsx",
        xlsx([("Sheet1", [["a", "b"], ["1", "2"], ["3", "4"]])], dimensions={"Sheet1": "A1:A1"}),
        {
            "rows": [["a", "b"], ["1", "2"], ["3", "4"]],
            "report": book_report(
                "xlsx", "Sheet1", ["Sheet1"], [["a", "b"], ["1", "2"], ["3", "4"]], []
            ),
        },
    )

    # Sheets.
    people = [["Name"], ["Ana"]]
    second = [["Name"], ["Carla"]]
    write(
        "sheets",
        "empty_first_sheet.xlsx",
        xlsx([("Cover", []), ("People", people)]),
        {"rows": people, "report": book_report("xlsx", "People", ["Cover", "People"], people, [])},
    )
    write(
        "sheets",
        "choose_by_name.xlsx",
        xlsx([("People", people), ("Other", second)]),
        {
            "rows": second,
            "report": book_report("xlsx", "Other", ["People", "Other"], second, []),
            "read_args": {"sheet": "Other"},
        },
    )
    write(
        "sheets",
        "choose_by_index.xlsx",
        xlsx([("People", people), ("Other", second)]),
        {
            "rows": second,
            "report": book_report("xlsx", "Other", ["People", "Other"], second, []),
            "read_args": {"sheet": 1},
        },
    )
    write(
        "sheets",
        "all_sheets_empty.xlsx",
        xlsx([("One", []), ("Two", [])]),
        {"rows": [], "report": book_report("xlsx", "One", ["One", "Two"], [], [])},
    )
    write(
        "sheets",
        "empty_first_sheet_legacy.xls",
        xls_books["second_sheet"],
        {
            "rows": [["Name"], ["Carla Dias"]],
            "report": book_report("xls", "Data", ["Cover", "Data"], [["Name"], ["Carla Dias"]], []),
        },
    )

    duration_expected = [["Worked"], ["37:45:30"], ["08:05:00"], ["2024-03-15T13:45:30"]]
    write(
        "workbook_cells",
        "duration_legacy.xls",
        xls_books["duration"],
        {
            "rows": duration_expected,
            "report": book_report("xls", "Hours", ["Hours"], duration_expected, []),
        },
    )

    # Merged cells.
    merged_rows = [
        ["Group", "Name"],
        ["North", "Ana"],
        [None, "Bruno"],
        [None, "Carla"],
        ["South", "Dora"],
    ]
    merged_expected = [
        ["Group", "Name"],
        ["North", "Ana"],
        ["North", "Bruno"],
        ["North", "Carla"],
        ["South", "Dora"],
    ]
    write(
        "merged",
        "vertical_group_label.xlsx",
        xlsx([("Sheet1", merged_rows)], merges={"Sheet1": ["A2:A4"]}),
        {
            "rows": merged_expected,
            "report": book_report(
                "xlsx", "Sheet1", ["Sheet1"], merged_expected, ["merged_cells_filled"]
            ),
        },
    )
    clipped_rows = [["Title", None, None], ["a", "b", "c"]]
    clipped_expected = [["Title", "Title", "Title"], ["a", "b", "c"]]
    write(
        "merged",
        "area_clipped_to_the_data.xlsx",
        xlsx([("Sheet1", clipped_rows)], merges={"Sheet1": ["A1:C1", "A5:Z900"]}),
        {
            "rows": clipped_expected,
            "report": book_report(
                "xlsx", "Sheet1", ["Sheet1"], clipped_expected, ["merged_cells_filled"]
            ),
        },
    )

    # Limits.
    bomb = declare_uncompressed_size(xlsx([("Sheet1", [["a"]])]), 2_000_000_000)
    write(
        "limits",
        "declares_two_gigabytes.xlsx",
        bomb,
        {"error": {"type": "LimitExceededError", "limit": "max_decompressed_bytes"}},
    )


if __name__ == "__main__":
    main()
