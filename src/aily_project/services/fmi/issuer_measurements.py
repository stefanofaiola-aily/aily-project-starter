"""Small, deterministic adapters for issuer tables stored in the shared DB.

Only recognised tables, units and period headers produce measurements. The
dossier supplies the requested subject and dates, never the source amounts.
Unrecognised or truncated documents stay evidence, not scoring observations.
"""

import re
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

from .extraction import DOCUMENT_RELATION
from .inputs import key
from .models import Row, calendar_date, fingerprint

# Verified source identifiers; these are not brand-to-parent revenue fallbacks.
ISSUERS = {
    "LVMHF",
    "PRDSY",
    "MONC.MI",
    "PVH",
    "RL",
    "BRBY.L",
    "hermes",
    "KER.PA",
    "TPR",
    "CPRI",
    "GAP",
    "ANF",
}
HOSTS = {
    "LVMHF": ("lvmh.com", "prismic.io"),
    "PRDSY": ("pradagroup.com",),
    "MONC.MI": ("monclergroup.com",),
    "PVH": ("pvh.com",),
    "RL": ("ralphlauren.com",),
    "BRBY.L": ("burberryplc.com",),
    "hermes": ("hermes.com", "hermesfinance.com"),
    "KER.PA": ("kering.com",),
    "TPR": ("tapestry.gcs-web.com",),
    "CPRI": ("s21.q4cdn.com", "s22.q4cdn.com", "capriholdings.com"),
    "GAP": ("s204.q4cdn.com", "gapinc.com"),
    "ANF": ("corporate.abercrombie.com",),
}
N = r"\d[\d,]*(?:\.\d+)?"
P = r"(?:[-+]?\d+%|\(\d+%\))"
D = r"[A-Z][a-z]+ \d{1,2} ?, 20\d{2}"


def issuer_date(value: str) -> date:
    return datetime.strptime(value.replace(" ,", ","), "%B %d, %Y").date()


def amount(value: str) -> float:
    return float(value.replace(",", ""))


def decode(document: Row) -> list[Row]:
    """Decode reviewed table layouts. Fail closed on changed source formats."""
    code = document.get("company_code")
    content = document.get("content")
    host = urlparse(str(document.get("url") or "")).hostname or ""
    if code not in HOSTS or not any(
        host == h or host.endswith("." + h) for h in HOSTS[code]
    ):
        return []
    if not isinstance(content, str) or not content.strip():
        return []
    if document.get("content_length") and len(content) < document["content_length"]:
        return []
    text = " ".join(content.split())
    result = []

    def emit(
        subject,
        scope,
        start,
        end,
        value,
        scale,
        currency,
        excerpt,
        *,
        boundaries_basis="explicit_calendar_year",
        boundaries_verified=True,
        fiscal_year_label=None,
    ):
        if value <= 0:
            return
        result.append(
            {
                "kind": "actual",
                "metric": "revenue",
                "financial_subject": subject,
                "scope": scope,
                "amount": value * scale,
                "currency": currency,
                "unit_multiplier": 1,
                "source_amount": value,
                "source_unit_multiplier": scale,
                "period_start": start,
                "period_end": end,
                "period_type": "annual" if (end - start).days > 300 else "quarter",
                "source_relation": DOCUMENT_RELATION,
                "source_row_id": fingerprint(
                    {
                        "document": document.get("source_row_id")
                        or fingerprint(document),
                        "subject": subject,
                        "start": start,
                        "end": end,
                        "amount": value * scale,
                    }
                ),
                "source_classification": "reported",
                "source_adapter": "issuer_tables_v1",
                "issuer_code": code,
                "source_document_id": document.get("source_row_id")
                or fingerprint(document),
                "source_url": document["url"],
                "evidence": excerpt,
                "extracted_at": document.get("extracted_at"),
                "crawled_at": document.get("crawled_at"),
                "published_at": document.get("created_at"),
                "available_at": None,
                "vintage_verified": False,
                "period_boundaries_basis": boundaries_basis,
                "period_boundaries_verified": boundaries_verified,
                "fiscal_year_label": fiscal_year_label,
            }
        )

    def annual(subject, scope, year, value, scale, excerpt):
        emit(
            subject,
            scope,
            date(year, 1, 1),
            date(year, 12, 31),
            value,
            scale,
            "EUR",
            excerpt,
        )

    def fiscal_pair(subject, scope, ends, values, scale, excerpt, *, year_offset=0):
        """Current annual start follows explicit prior year end, not calendar labels.

        The older start is an exposed 52-week inference, not eligible for quarterly
        aggregation. Another disclosure with its prior end supplies a verified start.
        """
        for index, (end, value) in enumerate(zip(ends, values, strict=True)):
            start = (
                ends[1] + timedelta(days=1) if index == 0 else end - timedelta(days=363)
            )
            emit(
                subject,
                scope,
                start,
                end,
                amount(value),
                scale,
                "USD",
                excerpt,
                boundaries_basis="annual_end_and_explicit_prior_end"
                if index == 0
                else "annual_end_with_inferred_52_week_start",
                boundaries_verified=index == 0,
                fiscal_year_label=f"FY{end.year + year_offset}",
            )

    if code == "LVMHF":
        # The financial-documents revenue table has year, prior year, changes,
        # and second-prior year. Never parse the following operating-profit table.
        block = re.search(
            r"Change in revenue by business group.*?\(\s*(?:EUR|€) millions.*?\) "
            r"(20\d{2}) (20\d{2}) \d{4}/\d{4} Change (20\d{2}) (.*?)"
            r"Profit from recurring operations",
            text,
            re.I,
        )
        if block:
            years = [int(block[i]) for i in (1, 2, 3)]
            for label, subject, scope in (
                (
                    "Fashion and Leather Goods",
                    "LVMH Fashion and Leather Goods",
                    "brand_segment",
                ),
                ("Total", "LVMH", "consolidated"),
            ):
                match = re.search(rf"{label} ({N}) ({N}) -?\d+% -?\d+% ({N})", block[4])
                if match:
                    for year, value in zip(years, match.groups(), strict=True):
                        annual(subject, scope, year, amount(value), 1e6, block[0])
    elif code == "PRDSY":
        block = re.search(
            rf"Key economic indicators \(amounts in thousands of Euro\) "
            rf"twelve months ended December 31 (20\d{{2}}) "
            rf"twelve months ended December 31 (20\d{{2}}) "
            rf"Net revenue\s*s? ({N}) ({N})",
            text,
            re.I,
        )
        if block:
            for y, v in ((block[1], block[3]), (block[2], block[4])):
                annual("Prada Group", "consolidated", int(y), amount(v), 1e3, block[0])
    elif code == "MONC.MI":
        block = re.search(
            r"GROUP CONSOLIDATED REVENUE\s*S\s*: EUR ([\d ,]+\.\s*\d+) million",
            text,
            re.I,
        )
        year = calendar_date(document["period_end"]).year
        if (
            block
            and calendar_date(document["period_end"]).month == 12
            and calendar_date(document["period_end"]).day == 31
            and re.search(rf"{year} GROUP REVENUES|Fiscal Year {year}", text, re.I)
        ):
            annual(
                "Moncler Group",
                "consolidated",
                year,
                amount(block[1].replace(" ", "")),
                1e6,
                block[0],
            )
        # Require a full discrete-quarter header and the MONCLER subtotal.
        # YTD (Q1/H1/9M/FY) and the separate Stone Island DTC tables fail closed.
        for table in re.finditer(
            r"Q1 (\d{2}) vs (\d{2}) Q2 \1 vs \2 Q3 \1 vs \2 Q4 \1 vs \2 "
            r"EUR m ((?:20\d{2} 20\d{2} cFX ){4})DTC (.*?) WHOLESALE (.*?) "
            r"(MONCLER|STONE ISLAND) ",
            text,
            re.I,
        ):
            years = (2000 + int(table[1]), 2000 + int(table[2]))
            if table[6].upper() != "MONCLER" or table[3].split() != [
                token
                for _ in range(4)
                for token in (str(years[0]), str(years[1]), "cFX")
            ]:
                continue
            values = re.fullmatch(
                rf"({N}) ({N}) {P} ({N}) ({N}) {P} "
                rf"({N}) ({N}) {P} ({N}) ({N}) {P}",
                table[4],
            )
            if not values:
                continue
            for quarter in range(4):
                for index, year in enumerate(years):
                    start = date(year, quarter * 3 + 1, 1)
                    end = (
                        date(year + 1, 1, 1)
                        if quarter == 3
                        else date(year, quarter * 3 + 4, 1)
                    ) - timedelta(days=1)
                    emit(
                        "Moncler",
                        "retail_dtc",
                        start,
                        end,
                        amount(values[quarter * 2 + index + 1]),
                        1e6,
                        "EUR",
                        table[0],
                        boundaries_basis="explicit_calendar_quarter_table",
                    )
    elif code == "PVH":
        block = re.search(
            r"REVENUE BY BRAND Quarter Ended Six Months Ended "
            r"(\d+/\d+/\d+) (\d+/\d+/\d+) (?:\d+/\d+/\d+ ){2}"
            r"(.*?) (?:Total Revenue|EARNINGS BEFORE)",
            text,
            re.I,
        )
        # USD millions is explicitly stated in PVH's GAAP statement header.
        if block and re.search(
            r"Consolidated GAAP Statements of Operations \(In millions", text
        ):
            ends = [
                date(2000 + int(y), int(m), int(d))
                for m, d, y in (s.split("/") for s in (block[1], block[2]))
            ]
            for label in ("Tommy Hilfiger", "Calvin Klein"):
                values = re.search(rf"{label} \$? ?({N}) \$? ?({N})", block[3])
                if values:
                    for end, value in zip(ends, values.groups(), strict=True):
                        emit(
                            label,
                            "brand_segment",
                            end - timedelta(days=90),
                            end,
                            amount(value),
                            1e6,
                            "USD",
                            block[0],
                            boundaries_basis="quarter_end_with_inferred_13_week_start",
                            boundaries_verified=False,
                        )
    elif code == "RL":
        block = re.search(
            rf"CONSOLIDATED STATEMENTS OF OPERATIONS .*?Three Months Ended "
            rf"Twelve Months Ended ({D}) ({D}) \1 \2 "
            rf"\(millions, except per share data\) Net revenues "
            rf"\$ ?({N}) \$ ?({N}) \$ ?({N}) \$ ?({N})",
            text,
        )
        if block:
            fiscal_pair(
                "Ralph Lauren",
                "consolidated",
                [issuer_date(block[1]), issuer_date(block[2])],
                [block[5], block[6]],
                1e6,
                block[0],
            )
        block = re.search(
            rf"CONSOLIDATED STATEMENTS OF OPERATIONS .*?Three Months Ended "
            rf"([A-Z][a-z]+ \d{{1,2}}, 20\d{{2}}) ([A-Z][a-z]+ \d{{1,2}}, 20\d{{2}}) "
            rf"\(millions, except per share data\) Net revenues \$ ({N}) \$ ({N})",
            text,
        )
        if block:
            for ending, value in ((block[1], block[3]), (block[2], block[4])):
                end = datetime.strptime(ending, "%B %d, %Y").date()
                emit(
                    "Ralph Lauren",
                    "consolidated",
                    end - timedelta(days=90),
                    end,
                    amount(value),
                    1e6,
                    "USD",
                    block[0],
                    boundaries_basis="quarter_end_with_inferred_13_week_start",
                    boundaries_verified=False,
                )
        retail = re.search(
            r"NET REVENUES BY SALES CHANNEL \(Unaudited\) Three Months Ended "
            r"(June \d{1,2}, 20\d{2}) (June \d{1,2}, 20\d{2}) "
            r"North America Europe Asia Other Total ?North America Europe Asia "
            r"Other Total \(millions\) Sales Channel: Retail (.*?) Wholesale",
            text,
        )
        if retail:
            cells = re.fullmatch(
                rf"\$ ?({N}) \$ ?({N}) \$ ?({N}) \$ ?— \$ ?({N}) "
                rf"\$ ?({N}) \$ ?({N}) \$ ?({N}) \$ ?— \$ ?({N})",
                retail[3],
            )
            if cells:
                for index in range(2):
                    numbers = [amount(cells[index * 4 + n]) for n in range(1, 5)]
                    end = datetime.strptime(retail[index + 1], "%B %d, %Y").date()
                    if end.weekday() != 5 or abs(sum(numbers[:3]) - numbers[3]) > 0.2:
                        continue
                    emit(
                        "Ralph Lauren",
                        "retail_dtc",
                        end - timedelta(days=90),
                        end,
                        numbers[3],
                        1e6,
                        "USD",
                        retail[0],
                        boundaries_basis="quarter_end_with_inferred_13_week_start",
                        boundaries_verified=False,
                    )
    elif code == "BRBY.L":
        # PDF text sometimes splits individual digits. Accept only this bounded
        # three-digit revenue layout; never collapse arbitrary numeric whitespace.
        day = r"\d(?: ?\d)?"
        year = r"20 ?\d ?\d"
        three_digits = r"\d(?: ?\d){2}"
        table = re.search(
            rf"RETAIL REVENUE 13 WEEKS ENDED {day} (?:JUNE|DECEMBER)(?: {year})? "
            rf"({day} (?:June|December)) ({day} (?:June|December)) % change "
            rf"£ million ({year}) ({year}) Reported FX CER ?\* "
            rf"Retail revenue ({three_digits}) ({three_digits}) "
            r"[-+]?\d+ ?% [-+]?\d+ ?%",
            text,
        )
        if table:
            for index in range(2):
                ending = re.sub(r"(?<=\d) (?=\d)", "", table[index + 1])
                ending += " " + table[index + 3].replace(" ", "")
                end = datetime.strptime(ending, "%d %B %Y").date()
                emit(
                    "Burberry",
                    "retail_dtc",
                    end - timedelta(days=90),
                    end,
                    amount(table[index + 5].replace(" ", "")),
                    1e6,
                    "GBP",
                    table[0],
                    boundaries_basis="explicit_13_week_table",
                )
    elif code == "hermes":
        block = re.search(
            rf"CONSOLIDATED INCOME STATEMENT In millions of euros "
            rf"(20\d{{2}}) (20\d{{2}}) Revenue ({N}) ({N})",
            text,
        )
        if block:
            for y, v in ((block[1], block[3]), (block[2], block[4])):
                annual("Hermès", "consolidated", int(y), amount(v), 1e6, block[0])
    elif code == "KER.PA":
        block = re.search(
            r"Revenue \(in € millions?\) (20\d{2}) (20\d{2}) "
            r"Reported change Comparable change.*? (Gucci.*?) "
            r"(?:Recurring operating income|Press release)",
            text,
        )
        if block:
            for label, subject in (
                ("Gucci", "Gucci"),
                ("Yves Saint Laurent", "Saint Laurent"),
            ):
                values = re.search(rf"{label} ({N}) ({N})", block[3])
                if values:
                    for year, value in zip(
                        (block[1], block[2]), values.groups(), strict=True
                    ):
                        annual(
                            subject,
                            "brand_segment",
                            int(year),
                            amount(value),
                            1e6,
                            block[0],
                        )
    elif code == "TPR":
        # Annual Detail to Net Sales, never the quarter or pro-forma group row.
        block = re.search(
            rf"DETAIL TO ?NET SALES .*?\(in millions\).*?YEAR ENDED "
            rf"({D}) ({D}) % Change Constant Currency % Change (.*?) "
            r"(?:Schedules|Schedule|1 Pro Forma)",
            text,
        )
        if block:
            ends = [issuer_date(block[1]), issuer_date(block[2])]
            for label in ("Coach", "Kate Spade"):
                values = re.search(rf"{label} \$? ?({N}) \$? ?({N})", block[3])
                if values:
                    fiscal_pair(
                        label, "brand_segment", ends, values.groups(), 1e6, block[0]
                    )
    elif code == "CPRI":
        # Keep brand revenue unchanged across the group's Versace disposal.
        block = re.search(
            rf"CONSOLIDATED REVENUE DATA \(\$ in millions\) \(Unaudited\) "
            rf"Three Months Ended Fiscal Years Ended ({D}) ({D}) \1 \2 "
            r"(.*?) SCHEDULE",
            text,
        )
        if block:
            ends = [issuer_date(block[1]), issuer_date(block[2])]
            values = re.search(
                rf"Michael Kors Revenue ({N}) ({N}) ({N}) ({N})", block[3]
            )
            if values:
                fiscal_pair(
                    "Michael Kors",
                    "brand_segment",
                    ends,
                    [values[3], values[4]],
                    1e6,
                    block[0],
                )
    elif code == "GAP":
        block = re.search(
            rf"CONSOLIDA ?TED ST ?ATEMENTS OF OPERA ?TIONS UNAUDITED "
            rf"13 W ?eeks Ended (?:14 W ?eeks Ended \(1\) )?"
            rf"52 W ?eeks Ended (?:53 W ?eeks Ended \(1\) )?"
            rf"\(\$ and shares in millions except per share amounts\)"
            rf"\s*({D}) ({D}) \1 \2 Net sales "
            rf"\$ ?({N}) \$ ?({N}) \$ ?({N}) \$ ?({N})",
            text,
        )
        if block:
            ends = [issuer_date(block[1]), issuer_date(block[2])]
            fiscal_pair(
                "GAP Inc",
                "consolidated",
                ends,
                [block[5], block[6]],
                1e6,
                block[0],
                year_offset=-1,
            )
            if "53 Weeks" in block[0]:
                result[-1].update(
                    period_start=ends[1] - timedelta(days=370),
                    period_boundaries_basis="explicit_53_week_annual_table",
                    period_boundaries_verified=True,
                )
    elif code == "ANF":
        block = re.search(
            rf"Consolidated Statements of Operations "
            rf"\(in thousands, except per share data\) \(Unaudited\) "
            rf"Fifty-Two Weeks Ended Fifty-(Two|Three) Weeks Ended "
            rf"({D})% of Net Sales ({D})% of Net Sales "
            rf"Net sales \$ ({N}) 100\.0 % \$ ({N}) 100\.0 %",
            text,
        )
        if block:
            ends = [issuer_date(block[2]), issuer_date(block[3])]
            fiscal_pair(
                "Abercrombie & Fitch",
                "consolidated",
                ends,
                [block[4], block[5]],
                1e3,
                block[0],
                year_offset=-1,
            )
            result[-1].update(
                period_start=ends[1]
                - timedelta(days=370 if block[1] == "Three" else 363),
                period_boundaries_basis="explicit_52_or_53_week_annual_table",
                period_boundaries_verified=True,
            )
    return result


def prepare_measurements(documents: list[Row]) -> list[Row]:
    """Deduplicate equal source observations; retain disagreements for selection."""
    rows = [r for d in documents for r in decode(d)]
    return list({r["source_row_id"]: r for r in rows}.values())


def matches_subject(row: Row, spec: Row) -> bool:
    """Explicit financial subjects, including separately labelled parent segments."""
    if row.get("source_adapter") != "issuer_tables_v1":
        return False

    def norm(s):
        return key(str(s)).replace("-", "")

    names = {norm(row.get("financial_subject"))}
    if row.get("financial_subject") == "LVMH":
        names.add(norm("LVMH consolidated group"))
    expected_scope = (
        "brand_segment" if spec.get("scope") == "parent_segment" else spec.get("scope")
    )
    return norm(spec.get("subject")) in names and expected_scope == row.get("scope")
