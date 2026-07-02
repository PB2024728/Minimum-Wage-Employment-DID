# FRED Series Validation Report - Project #4

_Generated: 2026-06-22T13:36:15.311146+00:00_

- Total series checked: **205**
- Resolved on FRED: **200**
- Missing / discontinued (dropped, not imputed): **5**
- Transient errors (rate-limit/network - NOT dropped, re-run to resolve): **0**

## Missing / discontinued series (dropped, not imputed)

| Jurisdiction | Role | Series ID | Error |
|---|---|---|---|
| AL | treatment | `STTMINWGAL` | ValueError: Bad Request.  The series does not exist. |
| LA | treatment | `STTMINWGLA` | ValueError: Bad Request.  The series does not exist. |
| MS | treatment | `STTMINWGMS` | ValueError: Bad Request.  The series does not exist. |
| SC | treatment | `STTMINWGSC` | ValueError: Bad Request.  The series does not exist. |
| TN | treatment | `STTMINWGTN` | ValueError: Bad Request.  The series does not exist. |

## Resolved series

| Jurisdiction | Role | Series ID | Freq | Units | Span |
|---|---|---|---|---|---|
| AK | treatment | `STTMINWGAK` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| AK | outcome | `AKLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| AK | normalizer | `AKNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| AK | control | `AKUR` | M | % | 1976-01-01 -> 2026-04-01 |
| AL | outcome | `ALLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| AL | normalizer | `ALNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| AL | control | `ALUR` | M | % | 1976-01-01 -> 2026-04-01 |
| AR | treatment | `STTMINWGAR` | A | $ per Hour | 1970-01-01 -> 2026-01-01 |
| AR | outcome | `ARLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| AR | normalizer | `ARNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| AR | control | `ARUR` | M | % | 1976-01-01 -> 2026-04-01 |
| AZ | treatment | `STTMINWGAZ` | A | $ per Hour | 2007-01-01 -> 2026-01-01 |
| AZ | outcome | `AZLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| AZ | normalizer | `AZNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| AZ | control | `AZUR` | M | % | 1976-01-01 -> 2026-04-01 |
| CA | treatment | `STTMINWGCA` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| CA | outcome | `CALEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| CA | normalizer | `CANA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| CA | control | `CAUR` | M | % | 1976-01-01 -> 2026-04-01 |
| CO | treatment | `STTMINWGCO` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| CO | outcome | `COLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| CO | normalizer | `CONA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| CO | control | `COUR` | M | % | 1976-01-01 -> 2026-04-01 |
| CT | treatment | `STTMINWGCT` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| CT | outcome | `CTLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| CT | normalizer | `CTNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| CT | control | `CTUR` | M | % | 1976-01-01 -> 2026-04-01 |
| DC | treatment | `STTMINWGDC` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| DC | outcome | `DCLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| DC | normalizer | `DCNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| DC | control | `DCUR` | M | % | 1976-01-01 -> 2026-04-01 |
| DE | treatment | `STTMINWGDE` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| DE | outcome | `DELEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| DE | normalizer | `DENA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| DE | control | `DEUR` | M | % | 1976-01-01 -> 2026-04-01 |
| FL | treatment | `STTMINWGFL` | A | $ per Hour | 2006-01-01 -> 2026-01-01 |
| FL | outcome | `FLLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| FL | normalizer | `FLNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| FL | control | `FLUR` | M | % | 1976-01-01 -> 2026-04-01 |
| GA | treatment | `STTMINWGGA` | A | $ per Hour | 1972-01-01 -> 2023-01-01 |
| GA | outcome | `GALEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| GA | normalizer | `GANA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| GA | control | `GAUR` | M | % | 1976-01-01 -> 2026-04-01 |
| HI | treatment | `STTMINWGHI` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| HI | outcome | `HILEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| HI | normalizer | `HINA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| HI | control | `HIUR` | M | % | 1976-01-01 -> 2026-04-01 |
| IA | treatment | `STTMINWGIA` | A | $ per Hour | 1991-01-01 -> 2026-01-01 |
| IA | outcome | `IALEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| IA | normalizer | `IANA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| IA | control | `IAUR` | M | % | 1976-01-01 -> 2026-04-01 |
| ID | treatment | `STTMINWGID` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| ID | outcome | `IDLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| ID | normalizer | `IDNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| ID | control | `IDUR` | M | % | 1976-01-01 -> 2026-04-01 |
| IL | treatment | `STTMINWGIL` | A | $ per Hour | 1972-01-01 -> 2026-01-01 |
| IL | outcome | `ILLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| IL | normalizer | `ILNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| IL | control | `ILUR` | M | % | 1976-01-01 -> 2026-04-01 |
| IN | treatment | `STTMINWGIN` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| IN | outcome | `INLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| IN | normalizer | `INNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| IN | control | `INUR` | M | % | 1976-01-01 -> 2026-04-01 |
| KS | treatment | `STTMINWGKS` | A | $ per Hour | 1979-01-01 -> 2026-01-01 |
| KS | outcome | `KSLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| KS | normalizer | `KSNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| KS | control | `KSUR` | M | % | 1976-01-01 -> 2026-04-01 |
| KY | treatment | `STTMINWGKY` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| KY | outcome | `KYLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| KY | normalizer | `KYNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| KY | control | `KYUR` | M | % | 1976-01-01 -> 2026-04-01 |
| LA | outcome | `LALEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| LA | normalizer | `LANA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| LA | control | `LAUR` | M | % | 1976-01-01 -> 2026-04-01 |
| MA | treatment | `STTMINWGMA` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| MA | outcome | `MALEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| MA | normalizer | `MANA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| MA | control | `MAUR` | M | % | 1976-01-01 -> 2026-04-01 |
| MD | treatment | `STTMINWGMD` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| MD | outcome | `MDLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| MD | normalizer | `MDNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| MD | control | `MDUR` | M | % | 1976-01-01 -> 2026-04-01 |
| ME | treatment | `STTMINWGME` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| ME | outcome | `MELEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| ME | normalizer | `MENA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| ME | control | `MEUR` | M | % | 1976-01-01 -> 2026-04-01 |
| MI | treatment | `STTMINWGMI` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| MI | outcome | `MILEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| MI | normalizer | `MINA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| MI | control | `MIUR` | M | % | 1976-01-01 -> 2026-04-01 |
| MN | treatment | `STTMINWGMN` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| MN | outcome | `MNLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| MN | normalizer | `MNNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| MN | control | `MNUR` | M | % | 1976-01-01 -> 2026-04-01 |
| MO | treatment | `STTMINWGMO` | A | $ per Hour | 1991-01-01 -> 2026-01-01 |
| MO | outcome | `MOLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| MO | normalizer | `MONA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| MO | control | `MOUR` | M | % | 1976-01-01 -> 2026-04-01 |
| MS | outcome | `MSLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| MS | normalizer | `MSNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| MS | control | `MSUR` | M | % | 1976-01-01 -> 2026-04-01 |
| MT | treatment | `STTMINWGMT` | A | $ per Hour | 1972-01-01 -> 2026-01-01 |
| MT | outcome | `MTLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| MT | normalizer | `MTNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| MT | control | `MTUR` | M | % | 1976-01-01 -> 2026-04-01 |
| NC | treatment | `STTMINWGNC` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| NC | outcome | `NCLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| NC | normalizer | `NCNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| NC | control | `NCUR` | M | % | 1976-01-01 -> 2026-04-01 |
| ND | treatment | `STTMINWGND` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| ND | outcome | `NDLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| ND | normalizer | `NDNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| ND | control | `NDUR` | M | % | 1976-01-01 -> 2026-04-01 |
| NE | treatment | `STTMINWGNE` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| NE | outcome | `NELEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| NE | normalizer | `NENA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| NE | control | `NEUR` | M | % | 1976-01-01 -> 2026-04-01 |
| NH | treatment | `STTMINWGNH` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| NH | outcome | `NHLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| NH | normalizer | `NHNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| NH | control | `NHUR` | M | % | 1976-01-01 -> 2026-04-01 |
| NJ | treatment | `STTMINWGNJ` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| NJ | outcome | `NJLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| NJ | normalizer | `NJNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| NJ | control | `NJUR` | M | % | 1976-01-01 -> 2026-04-01 |
| NM | treatment | `STTMINWGNM` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| NM | outcome | `NMLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| NM | normalizer | `NMNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| NM | control | `NMUR` | M | % | 1976-01-01 -> 2026-04-01 |
| NV | treatment | `STTMINWGNV` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| NV | outcome | `NVLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| NV | normalizer | `NVNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| NV | control | `NVUR` | M | % | 1976-01-01 -> 2026-04-01 |
| NY | treatment | `STTMINWGNY` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| NY | outcome | `NYLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| NY | normalizer | `NYNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| NY | control | `NYUR` | M | % | 1976-01-01 -> 2026-04-01 |
| OH | treatment | `STTMINWGOH` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| OH | outcome | `OHLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| OH | normalizer | `OHNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| OH | control | `OHUR` | M | % | 1976-01-01 -> 2026-04-01 |
| OK | treatment | `STTMINWGOK` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| OK | outcome | `OKLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| OK | normalizer | `OKNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| OK | control | `OKUR` | M | % | 1976-01-01 -> 2026-04-01 |
| OR | treatment | `STTMINWGOR` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| OR | outcome | `ORLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| OR | normalizer | `ORNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| OR | control | `ORUR` | M | % | 1976-01-01 -> 2026-04-01 |
| PA | treatment | `STTMINWGPA` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| PA | outcome | `PALEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| PA | normalizer | `PANA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| PA | control | `PAUR` | M | % | 1976-01-01 -> 2026-04-01 |
| RI | treatment | `STTMINWGRI` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| RI | outcome | `RILEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| RI | normalizer | `RINA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| RI | control | `RIUR` | M | % | 1976-01-01 -> 2026-04-01 |
| SC | outcome | `SCLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| SC | normalizer | `SCNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| SC | control | `SCUR` | M | % | 1976-01-01 -> 2026-04-01 |
| SD | treatment | `STTMINWGSD` | A | $ per Hour | 1970-01-01 -> 2026-01-01 |
| SD | outcome | `SDLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| SD | normalizer | `SDNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| SD | control | `SDUR` | M | % | 1976-01-01 -> 2026-04-01 |
| TN | outcome | `TNLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| TN | normalizer | `TNNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| TN | control | `TNUR` | M | % | 1976-01-01 -> 2026-04-01 |
| TX | treatment | `STTMINWGTX` | A | $ per Hour | 1972-01-01 -> 2026-01-01 |
| TX | outcome | `TXLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| TX | normalizer | `TXNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| TX | control | `TXUR` | M | % | 1976-01-01 -> 2026-04-01 |
| UT | treatment | `STTMINWGUT` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| UT | outcome | `UTLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| UT | normalizer | `UTNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| UT | control | `UTUR` | M | % | 1976-01-01 -> 2026-04-01 |
| VA | treatment | `STTMINWGVA` | A | $ per Hour | 1976-01-01 -> 2026-01-01 |
| VA | outcome | `VALEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| VA | normalizer | `VANA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| VA | control | `VAUR` | M | % | 1976-01-01 -> 2026-04-01 |
| VT | treatment | `STTMINWGVT` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| VT | outcome | `VTLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| VT | normalizer | `VTNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| VT | control | `VTUR` | M | % | 1976-01-01 -> 2026-04-01 |
| WA | treatment | `STTMINWGWA` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| WA | outcome | `WALEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| WA | normalizer | `WANA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| WA | control | `WAUR` | M | % | 1976-01-01 -> 2026-04-01 |
| WI | treatment | `STTMINWGWI` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| WI | outcome | `WILEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| WI | normalizer | `WINA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| WI | control | `WIUR` | M | % | 1976-01-01 -> 2026-04-01 |
| WV | treatment | `STTMINWGWV` | A | $ per Hour | 1968-01-01 -> 2026-01-01 |
| WV | outcome | `WVLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| WV | normalizer | `WVNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| WV | control | `WVUR` | M | % | 1976-01-01 -> 2026-04-01 |
| WY | treatment | `STTMINWGWY` | A | $ per Hour | 1968-01-01 -> 2023-01-01 |
| WY | outcome | `WYLEIH` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| WY | normalizer | `WYNA` | M | Thous. of Persons | 1990-01-01 -> 2026-04-01 |
| WY | control | `WYUR` | M | % | 1976-01-01 -> 2026-04-01 |
| US | federal_min_wage | `FEDMINNFRWG` | M | $ per Hour | 1938-10-01 -> 2026-05-01 |