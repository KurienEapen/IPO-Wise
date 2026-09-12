import requests
import json
import re
import html
import math
from datetime import datetime
import pytz
from typing import List, Dict, Any, Optional

class InvestorGainScraper:
    BASE_URL_TEMPLATE = "https://webnodejs.investorgain.com/cloud/v2/report/data-read/{report_id}/1/{month}/{year}/{fin_year}/0/all"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.investorgain.com/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9"
        }
        self.params = {
            "search": "",
            "v": "17-18"
        }

    def _get_dates(self):
        now = datetime.now()
        month = now.month
        year = now.year
        if month >= 4:
            fin_year = f"{year}-{str(year + 1)[-2:]}"
        else:
            fin_year = f"{year - 1}-{str(year)[-2:]}"
        return month, year, fin_year

    def fetch_raw_reports(self) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        month, year, fin_year = self._get_dates()
        gmp_url = self.BASE_URL_TEMPLATE.format(report_id=331, month=month, year=year, fin_year=fin_year)
        sub_url = self.BASE_URL_TEMPLATE.format(report_id=333, month=month, year=year, fin_year=fin_year)

        gmp_data = []
        sub_data = []

        try:
            r331 = requests.get(gmp_url, params=self.params, headers=self.headers, timeout=20)
            if r331.status_code == 200:
                gmp_data = r331.json().get("reportTableData", [])
        except Exception as e:
            print(f"[InvestorGainScraper] Error fetching Report 331: {e}")

        try:
            r333 = requests.get(sub_url, params=self.params, headers=self.headers, timeout=20)
            if r333.status_code == 200:
                sub_data = r333.json().get("reportTableData", [])
        except Exception as e:
            print(f"[InvestorGainScraper] Error fetching Report 333: {e}")

        return gmp_data, sub_data

    @staticmethod
    def _clean_html(text: str) -> str:
        if not text:
            return ""
        decoded = html.unescape(str(text))
        return re.sub(r"<[^>]+>", "", decoded).strip()

    @staticmethod
    def _extract_number(val: Any) -> Optional[float]:
        if val is None:
            return None
        s = InvestorGainScraper._clean_html(str(val)).replace(",", "").replace("₹", "").replace("%", "").strip()
        m = re.search(r"[-+]?\d*\.?\d+", s)
        if m:
            try:
                return float(m.group(0))
            except ValueError:
                return None
        return None

    def parse_all_ipos(self) -> List[Dict[str, Any]]:
        gmp_data, sub_data = self.fetch_raw_reports()
        sub_map = {item.get("~id"): item for item in sub_data if item.get("~id")}

        result = []
        for item in gmp_data:
            parsed = self._normalize_ipo_data(item, sub_map.get(item.get("~id"), {}))
            if parsed:
                result.append(parsed)
        return result

    def _normalize_ipo_data(self, gmp_item: Dict[str, Any], sub_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            ipo_id = gmp_item.get("~id")
            name = gmp_item.get("~ipo_name") or self._clean_html(gmp_item.get("Name", "Unknown"))
            if not name or name == "Unknown":
                return None

            category = gmp_item.get("~IPO_Category") or gmp_item.get("~ipo_category1") or "Mainboard"

            # Dates
            raw_start = gmp_item.get("Open") or gmp_item.get("~Srt_Open") or "TBA"
            raw_end = gmp_item.get("Close") or gmp_item.get("~Srt_Close") or "TBA"
            if raw_end == "TBA" and sub_item.get("Closing Date"):
                raw_end = sub_item.get("Closing Date")

            start_date = self._clean_html(str(raw_start)).split("\n")[0].split("GMP:")[0].strip()
            end_date = self._clean_html(str(raw_end)).split("\n")[0].split("GMP:")[0].strip()
            start_date_sort = str(gmp_item.get("~Srt_Open") or "").strip()
            end_date_sort = str(gmp_item.get("~Srt_Close") or "").strip()

            # Current date and time in IST
            try:
                now_ist = datetime.now(pytz.timezone("Asia/Kolkata"))
            except Exception:
                now_ist = datetime.now()
            today_ist = now_ist.strftime("%Y-%m-%d")

            status_code = gmp_item.get("~ipo_status1", "").upper()
            status_map = {
                "O": "OPEN",
                "CT": "CLOSING_TODAY",
                "U": "UPCOMING",
                "C": "CLOSED",
                "LN": "LISTED_NEW",
                "LP": "LISTED_PAST"
            }

            # Check if closing today
            is_closing_date = (end_date_sort == today_ist)
            is_closing_today = (status_code == "CT") or is_closing_date

            if status_code == "CT":
                status = "CLOSING_TODAY"
                is_open = True
                is_closing_today = True
            elif status_code == "O":
                if is_closing_date:
                    status = "CLOSING_TODAY"
                    is_closing_today = True
                else:
                    status = "OPEN"
                is_open = True
            elif status_code == "C" and is_closing_date and now_ist.hour < 17:
                # Market bidding is still active on closing date before 5 PM IST cutoff
                status = "CLOSING_TODAY"
                is_open = True
                is_closing_today = True
            else:
                status = status_map.get(status_code, status_code or "UNKNOWN")
                is_open = False

            # GMP Extraction
            gmp_raw = gmp_item.get("GMP", "")
            gmp_clean = self._clean_html(gmp_raw)
            # Find rupee amount
            gmp_val_match = re.search(r"₹\s*([0-9\.\-]+)", gmp_clean)
            if not gmp_val_match:
                gmp_val_match = re.search(r"[-+]?\d+", gmp_clean)
            gmp_val_str = f"₹{gmp_val_match.group(1)}" if gmp_val_match else "₹0"

            # GMP Percentage
            gmp_pct_match = re.search(r"\(([\d\.]+)%\)", gmp_raw)
            if gmp_pct_match:
                gmp_percent = float(gmp_pct_match.group(1))
            else:
                pct_calc = self._extract_number(gmp_item.get("~gmp_percent_calc"))
                gmp_percent = pct_calc if pct_calc is not None else 0.0

            # Price & Lot
            price_raw = gmp_item.get("Price (₹)") or sub_item.get("IPO Price") or ""
            price_str = self._clean_html(str(price_raw))
            # Find numbers in price
            price_numbers = [float(x) for x in re.findall(r"\d+\.?\d*", price_str)]
            cutoff_price = max(price_numbers) if price_numbers else 0.0

            lot_raw = gmp_item.get("Lot") or ""
            lot_clean = self._extract_number(lot_raw)
            lot_size = int(lot_clean) if lot_clean and lot_clean > 0 else 0

            # Subscriptions
            def get_sub_val(val_raw) -> str:
                if not val_raw:
                    return "-"
                cleaned = self._clean_html(str(val_raw)).split("<br>")[0].strip()
                num = self._extract_number(cleaned)
                return f"{num:.2f}x" if num is not None else (cleaned if cleaned else "-")

            qib_sub = get_sub_val(sub_item.get("QIB"))
            hni_sub = get_sub_val(sub_item.get("NII") or sub_item.get("SHNI"))
            retail_sub = get_sub_val(sub_item.get("RII"))
            total_sub = get_sub_val(sub_item.get("Total") or gmp_item.get("Sub"))

            # Order Quantities
            retail_min_order = "1 Lot"
            hni_min_order = "2 Lots"

            if lot_size > 0 and cutoff_price > 0:
                retail_amount = lot_size * cutoff_price
                retail_min_order = f"1 Lot ({lot_size:,} shares) • ₹{int(retail_amount):,}"

                if category.upper() == "SME":
                    # SME HNI is generally 2 lots (minimum application > ₹2 Lakhs)
                    hni_lots = 2
                else:
                    # Mainline: minimum lots to cross ₹2,00,000 for sHNI
                    hni_lots = max(2, math.ceil(200001 / (lot_size * cutoff_price)))
                
                hni_shares = hni_lots * lot_size
                hni_amount = hni_shares * cutoff_price
                hni_min_order = f"{hni_lots} Lots ({hni_shares:,} shares) • ₹{int(hni_amount):,}"
            elif lot_size > 0:
                retail_min_order = f"1 Lot ({lot_size:,} shares)"
                hni_min_order = f"2 Lots ({lot_size * 2:,} shares)"

            return {
                "id": ipo_id,
                "name": name.strip(),
                "category": category,
                "status": status,
                "is_open": is_open,
                "is_closing_today": is_closing_today,
                "start_date": start_date,
                "end_date": end_date,
                "start_date_sort": start_date_sort,
                "end_date_sort": end_date_sort,
                "gmp_val": gmp_val_str,
                "gmp_percent": round(gmp_percent, 2),
                "price": price_str if price_str else (f"₹{cutoff_price:.0f}" if cutoff_price else "TBA"),
                "cutoff_price": cutoff_price,
                "lot_size": lot_size,
                "qib_sub": qib_sub,
                "hni_sub": hni_sub,
                "retail_sub": retail_sub,
                "total_sub": total_sub,
                "retail_min_order": retail_min_order,
                "hni_min_order": hni_min_order,
                "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        except Exception as e:
            print(f"[InvestorGainScraper] Error parsing item {gmp_item.get('~ipo_name')}: {e}")
            return None

    def get_open_ipos_above_gmp(self, min_gmp_percent: float = 15.0) -> List[Dict[str, Any]]:
        all_ipos = self.parse_all_ipos()
        return [
            ipo for ipo in all_ipos
            if ipo["is_open"] and ipo["gmp_percent"] >= min_gmp_percent
        ]
