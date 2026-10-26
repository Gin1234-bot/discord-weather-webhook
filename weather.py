import os
import sys
import re
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
import requests

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Múi giờ Việt Nam: UTC+7
TZ = timezone(timedelta(hours=7))

WEEKDAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]

# Tải Webhook URL từ biến môi trường hoặc file .env
WEBHOOK = os.getenv("DISCORD_WEBHOOK")
if not WEBHOOK and os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("DISCORD_WEBHOOK="):
                WEBHOOK = line.split("=", 1)[1].strip().strip('"').strip("'")

if not WEBHOOK:
    print("[!] Lỗi: Chưa cấu hình DISCORD_WEBHOOK trong .env!")
    sys.exit(1)

STATE_FILE = "state.json"

# Cấu trúc 36 tỉnh thành đồng bộ kích thước cân đối giữa 3 miền (Mỗi miền đúng 12 tỉnh, 2 tiểu vùng x 6 tỉnh)
PROVINCES_CONFIG = {
    "🏔️ KHU VỰC MIỀN BẮC": {
        "color": 0x3498DB,  # Xanh lam
        "subregions": {
            "🏛️ ĐỒNG BẰNG SÔNG HỒNG & DUYÊN HẢI": [
                ("Hà Nội", 21.03, 105.85),
                ("Hải Phòng", 20.86, 106.68),
                ("Quảng Ninh", 20.95, 107.08),
                ("Nam Định", 20.43, 106.17),
                ("Ninh Bình", 20.25, 105.97),
                ("Phú Thọ", 21.32, 105.40),
            ],
            "🏔️ VÙNG NÚI TÂY BẮC & ĐÔNG BẮC": [
                ("Sa Pa (Lào Cai)", 22.48, 103.97),
                ("Điện Biên", 21.38, 103.02),
                ("Sơn La", 21.33, 103.91),
                ("Thái Nguyên", 21.59, 105.84),
                ("Bắc Giang", 21.27, 106.19),
                ("Lạng Sơn", 21.85, 106.76),
            ]
        }
    },
    "🏖️ KHU VỰC MIỀN TRUNG & TÂY NGUYÊN": {
        "color": 0xE67E22,  # Vàng cam
        "subregions": {
            "🌊 BẮC TRUNG BỘ & DUYÊN HẢI": [
                ("Thanh Hóa", 19.81, 105.78),
                ("Nghệ An", 18.67, 105.68),
                ("Hà Tĩnh", 18.34, 105.90),
                ("Quảng Bình", 17.47, 106.60),
                ("Huế", 16.46, 107.59),
                ("Đà Nẵng", 16.05, 108.20),
            ],
            "🌲 NAM TRUNG BỘ & TÂY NGUYÊN": [
                ("Quảng Nam", 15.57, 108.48),
                ("Quảng Ngãi", 15.12, 108.80),
                ("Quy Nhơn (Bình Định)", 13.78, 109.22),
                ("Nha Trang (Khánh Hòa)", 12.24, 109.19),
                ("Đà Lạt (Lâm Đồng)", 11.94, 108.44),
                ("Buôn Ma Thuột (Đắk Lắk)", 12.67, 108.04),
            ]
        }
    },
    "🌴 KHU VỰC MIỀN NAM & ĐBSCL": {
        "color": 0x2ECC71,  # Xanh lục
        "subregions": {
            "🏙️ ĐÔNG NAM BỘ": [
                ("TP. Hồ Chí Minh", 10.82, 106.63),
                ("Bình Dương", 10.98, 106.65),
                ("Đồng Nai", 10.95, 106.82),
                ("Vũng Tàu", 10.35, 107.08),
                ("Tây Ninh", 11.31, 106.10),
                ("Bình Phước", 11.53, 106.88),
            ],
            "🌾 ĐỒNG BẰNG SÔNG CỬU LONG": [
                ("Cần Thơ", 10.03, 105.78),
                ("Long An", 10.53, 106.41),
                ("Tiền Giang", 10.36, 106.36),
                ("An Giang", 10.38, 105.43),
                ("Kiên Giang", 10.01, 105.08),
                ("Cà Mau", 9.18, 105.15),
            ]
        }
    }
}

HEAT = ["", "Nắng nóng", "Nắng nóng gay gắt", "Nắng nóng đặc biệt gay gắt"]
FOOTER = {"text": "Dữ liệu: Open-Meteo & GDACS • Tự động gửi qua Webhook"}

def beaufort(kmh):
    tops = [1, 5, 11, 19, 28, 38, 49, 61, 74, 88, 102, 117, 133, 149, 166, 183, 201, 220]
    for lvl, top in enumerate(tops):
        if kmh <= top:
            return lvl
    return 17

def heat_level(t):
    return 3 if t >= 39 else 2 if t >= 37 else 1 if t >= 35 else 0

def mo_ta(c, tmax):
    if c in (0, 1): return "☀️ Nắng ráo" if tmax >= 35 else "🌤️ Nắng nhẹ"
    if c in (2, 3): return "⛅ Nhiều mây"
    if c in (45, 48): return "🌫️ Sương mù"
    if 51 <= c <= 67 or 80 <= c <= 82: return "🌧️ Mưa rào"
    if c >= 95: return "⛈️ Có dông"
    return "🌥️ Trời âm u"

def fetch_all_provinces():
    all_lats, all_lons = [], []
    name_order = []
    
    for region, rdata in PROVINCES_CONFIG.items():
        for subregion, provs in rdata["subregions"].items():
            for name, lat, lon in provs:
                all_lats.append(str(lat))
                all_lons.append(str(lon))
                name_order.append((region, subregion, name))

    params = {
        "latitude": ",".join(all_lats),
        "longitude": ",".join(all_lons),
        "hourly": "precipitation_probability,precipitation,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min",
        "timezone": "Asia/Bangkok",
        "forecast_days": 2,
    }
    
    r = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=30)
    r.raise_for_status()
    raw_results = r.json()
    
    mapped = {}
    for i, (region, subregion, name) in enumerate(name_order):
        if region not in mapped:
            mapped[region] = {}
        if subregion not in mapped[region]:
            mapped[region][subregion] = {}
        mapped[region][subregion][name] = raw_results[i]
        
    return mapped

def analyze(data, now):
    h, d = data["hourly"], data["daily"]
    start = now.replace(minute=0, second=0, microsecond=0)
    win = [i for i, t in enumerate(h["time"])
           if 0 <= (datetime.fromisoformat(t).replace(tzinfo=TZ) - start).total_seconds() < 12 * 3600]
    wet = [i for i in win
           if (h["precipitation_probability"][i] or 0) >= 60 and (h["precipitation"][i] or 0) >= 0.3]
    rain = None
    if wet:
        rain = (datetime.fromisoformat(h["time"][wet[0]]).hour,
                datetime.fromisoformat(h["time"][wet[-1]]).hour + 1)
    wind = max(h["wind_speed_10m"][i] or 0 for i in win) if win else 0
    tmax = d["temperature_2m_max"][0]
    return {
        "tmin": d["temperature_2m_min"][0],
        "tmax": tmax,
        "code": d["weather_code"][0],
        "rain": rain,
        "wind": wind,
        "cap": beaufort(wind),
        "heat": heat_level(tmax)
    }

def storms():
    out = []
    ns = "{http://www.gdacs.org}"
    try:
        r = requests.get("https://www.gdacs.org/xml/rss.xml", timeout=25)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        now_utc = datetime.now(timezone.utc)
        
        # Chỉ theo dõi bão tại Việt Nam, Vịnh Bắc Bộ và vùng Biển Đông
        keywords = ["vietnam", "viet nam", "bien dong", "south china sea", "gulf of tonkin", "vịnh bắc bộ"]
        
        for it in root.iter("item"):
            if it.findtext(ns + "eventtype") != "TC":
                continue
            
            country = it.findtext(ns + "country") or ""
            title = it.findtext("title") or ""
            desc = it.findtext("description") or ""
            combined = f"{country} {title} {desc}".lower()
            
            # Tọa độ tâm bão nếu có trong feed
            point_str = it.findtext("{http://www.georss.org/georss}point") or ""
            in_vn_sea = False
            if point_str:
                try:
                    lat, lon = [float(x) for x in point_str.strip().split()]
                    # Phạm vi Biển Đông và lân cận Việt Nam (5 - 24°N, 102 - 120°E)
                    if 5.0 <= lat <= 24.0 and 102.0 <= lon <= 120.0:
                        in_vn_sea = True
                except Exception:
                    pass

            affects_vn = any(k in combined for k in keywords) or in_vn_sea
            if not affects_vn:
                continue

            # Kiểm tra bão còn đang hoạt động không (bỏ qua nếu todate đã kết thúc quá 24h)
            todate_str = it.findtext(ns + "todate")
            if todate_str:
                try:
                    t_end = datetime.strptime(todate_str.replace(" GMT", ""), "%a, %d %b %Y %H:%M:%S").replace(tzinfo=timezone.utc)
                    if (now_utc - t_end).total_seconds() > 24 * 3600:
                        continue
                except Exception:
                    pass

            eventname = it.findtext(ns + "eventname") or "Chưa rõ tên"
            sev = it.find(ns + "severity")
            stext = sev.text if sev is not None and sev.text else ""
            km = re.search(r"(\d+)\s*km/h", stext)
            wind_kmh = int(km.group(1)) if km else 0
            out.append((eventname, stext, wind_kmh))
    except Exception as e:
        print(f"[!] Lỗi bão GDACS: {e}")
    return out

def load_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_state(s):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[!] Lỗi lưu state: {e}")

def post(content, embeds):
    payload = {"content": content, "embeds": embeds}
    r = requests.post(WEBHOOK, json=payload, timeout=25)
    r.raise_for_status()
    print("[+] Đã gửi thành công vào Discord!")

def main(mode="morning"):
    now = datetime.now(TZ)
    print(f"[*] Bắt đầu phiên chạy: [{mode}] lúc {now.strftime('%d/%m/%Y %H:%M:%S')} (Quét 36 tỉnh đồng bộ 3 miền)...")

    state = load_state()
    today = now.strftime("%Y-%m-%d")
    if state.get("date") != today:
        state["date"] = today
        state["v"] = {}
    state.setdefault("storms", {})

    print("[*] Đang lấy dữ liệu từ Open-Meteo...")
    raw_data = fetch_all_provinces()

    analyzed = {}
    for region, sdict in raw_data.items():
        analyzed[region] = {}
        for subregion, pdict in sdict.items():
            analyzed[region][subregion] = {}
            for pname, pdata in pdict.items():
                analyzed[region][subregion][pname] = analyze(pdata, now)

    v = state["v"]

    thu = WEEKDAYS[now.weekday()]
    date_str = now.strftime("%d/%m/%Y")
    time_str = now.strftime("%H:%M")
    ts = int(now.timestamp())

    if mode in ("morning", "test"):
        embeds = []

        for region, sdict in analyzed.items():
            section_blocks = []
            
            for subregion, pdict in sdict.items():
                lines = [f"**{subregion}**"]
                for pname, a in pdict.items():
                    rain_text = f"🌧️ Mưa {a['rain'][0]}h–{a['rain'][1]}h" if a["rain"] else "☂️ Tạnh ráo"
                    heat_text = f" • 🔥 **{HEAT[a['heat']]}**" if a["heat"] else ""
                    wind_text = f" • 💨 Cấp {a['cap']}" if a["cap"] >= 4 else ""
                    
                    # Bỏ icon thanh nhiệt độ đỏ, chỉ để nhiệt độ gọn gàng
                    row = f"• **{pname}:** {mo_ta(a['code'], a['tmax'])}{heat_text} • `{a['tmin']:.0f}–{a['tmax']:.0f}°C` • {rain_text}{wind_text}"
                    lines.append(row)
                    
                    # Lưu state
                    v[f"rain:{pname}"] = a["rain"][0] if a["rain"] else "none"
                    v[f"heat:{pname}"] = a["heat"]
                    v[f"wind:{pname}"] = a["cap"]
                    
                section_blocks.append("\n".join(lines))

            desc_content = "\n\n".join(section_blocks)

            embed = {
                "title": f"{region}",
                "description": desc_content,
                "color": PROVINCES_CONFIG[region]["color"],
            }
            embeds.append(embed)

        # Cảnh báo bão thực tế nếu có (chỉ hiện khi có bão thật sự đe dọa Việt Nam/Biển Đông)
        storm_list = storms()
        if storm_list:
            s_lines = [f"⚠️ **Bão {name}**: {stext} (Gió giật cấp ~{beaufort(kmh)})" for name, stext, kmh in storm_list]
            embeds.append({
                "title": "🌀 CẢNH BÁO BÃO KHẨN CẤP (BIỂN ĐÔNG / VIỆT NAM)",
                "description": "\n\n".join(s_lines),
                "color": 0xE74C3C, # Đỏ cảnh báo
            })

        embeds[-1]["footer"] = FOOTER
        embeds[-1]["timestamp"] = now.isoformat()

        ping_prefix = "@everyone " if mode == "morning" else ""
        content = (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{ping_prefix}🌅 **BẢN TIN DỰ BÁO THỜI TIẾT • {thu.upper()}, {date_str}**\n"
            f"⏰ *Phát sóng lúc: {time_str} (Giờ Việt Nam)* • <t:{ts}:R>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        post(content, embeds)

    elif mode == "check":
        alerts = []
        severe = False

        for region, sdict in analyzed.items():
            for subregion, pdict in sdict.items():
                for pname, a in pdict.items():
                    tag = f"**{pname}**"
                    if a["rain"] and v.get(f"rain:{pname}", "none") == "none":
                        alerts.append(f"🌧️ 📍 {tag}: Dự báo xuất hiện mưa từ khoảng **{a['rain'][0]}h – {a['rain'][1]}h**.")
                    if a["heat"] > v.get(f"heat:{pname}", 0):
                        alerts.append(f"🔥 📍 {tag}: Nắng gắt gia tăng, đạt **{HEAT[a['heat']]}** (Đỉnh điểm **{a['tmax']:.0f}°C**).")
                        severe |= a["heat"] >= 2
                    if a["cap"] >= 6 and a["cap"] > v.get(f"wind:{pname}", 0):
                        alerts.append(f"💨 📍 {tag}: Gió mạnh bất thường đạt **Cấp {a['cap']}** ({a['wind']:.0f} km/h).")
                        severe |= a["cap"] >= 8
                    
                    v[f"rain:{pname}"] = a["rain"][0] if a["rain"] else "none"
                    v[f"heat:{pname}"] = a["heat"]
                    v[f"wind:{pname}"] = a["cap"]

        try:
            for name, stext, kmh in storms():
                cap = beaufort(kmh)
                prev = state["storms"].get(name)
                if prev is None or cap > prev:
                    alerts.append(f"🌀 Bão **{name}** có chuyển biến mới! {stext} (Gió cấp ~{cap}).")
                    severe = True
                state["storms"][name] = cap
        except Exception as e:
            print(f"[!] Lỗi bão GDACS: {e}")

        if alerts:
            quiet = now.hour < 6 or now.hour >= 23
            ping = "@everyone " if severe and not quiet else ""
            embed = {
                "title": "⚠️ CẢNH BÁO BIẾN ĐỘNG THỜI TIẾT TẠI CÁC TỈNH",
                "description": "\n\n".join(alerts[:15]),
                "color": 0xE74C3C if severe else 0x3498DB,
                "footer": FOOTER,
                "timestamp": now.isoformat()
            }
            content = (
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{ping}⚠️ **CẢNH BÁO BIẾN ĐỘNG THỜI TIẾT • {thu.upper()}, {date_str}**\n"
                f"⏰ *Ghi nhận lúc: {time_str} (Giờ Việt Nam)* • <t:{ts}:R>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
            post(content, [embed])
        else:
            print("[*] Các tỉnh đều ổn định, không có biến động bất thường.")

    save_state(state)
    print("[+] Hoàn tất phiên chạy.")

if __name__ == "__main__":
    run_mode = sys.argv[1] if len(sys.argv) > 1 else "morning"
    main(run_mode)
