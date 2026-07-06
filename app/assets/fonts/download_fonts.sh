#!/usr/bin/env bash
# ============================================================
# VibeMix 字体下载脚本
# 将卡片模板所需的特殊字体下载到当前目录
# 用法：cd app/assets/fonts && bash download_fonts.sh
# ============================================================
set -e

FONTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API="https://fonts.googleapis.com/css2"
UA="Mozilla/5.0 (X11; Linux x86_64)"

download_ttf() {
  local name="$1"
  local url="$2"
  if [ -f "${FONTS_DIR}/${name}" ]; then
    echo "[skip] ${name} already exists"
    return
  fi
  echo "[download] ${name}"
  curl -fsSL -A "${UA}" "${url}" -o "${FONTS_DIR}/${name}"
}

# ── Noto Sans SC（多字重）─────────────────────────────────────────────────────
# 从 Google Fonts 下载 TTF
for weight in 100 300 400 500 700 900; do
  css_url="${API}?family=Noto+Sans+SC:wght@${weight}&display=swap"
  ttf_url=$(curl -fsSL -A "${UA}" "${css_url}" | grep -oP "(?<=url\()https://[^)]+\.ttf" | head -1)
  [ -n "${ttf_url}" ] && download_ttf "NotoSansSC-w${weight}.ttf" "${ttf_url}" || \
    echo "[warn] Could not resolve Noto Sans SC weight ${weight}"
done

# 重命名为 service 期望的文件名
[ -f "NotoSansSC-w100.ttf" ] && cp "NotoSansSC-w100.ttf" "NotoSansSC-Thin.ttf"
[ -f "NotoSansSC-w300.ttf" ] && cp "NotoSansSC-w300.ttf" "NotoSansSC-Light.ttf"
[ -f "NotoSansSC-w400.ttf" ] && cp "NotoSansSC-w400.ttf" "NotoSansSC-Regular.ttf"
[ -f "NotoSansSC-w500.ttf" ] && cp "NotoSansSC-w500.ttf" "NotoSansSC-Medium.ttf"
[ -f "NotoSansSC-w700.ttf" ] && cp "NotoSansSC-w700.ttf" "NotoSansSC-Bold.ttf"
[ -f "NotoSansSC-w900.ttf" ] && cp "NotoSansSC-w900.ttf" "NotoSansSC-Black.ttf"

# ── Noto Serif SC ─────────────────────────────────────────────────────────────
for weight in 400 600 700; do
  css_url="${API}?family=Noto+Serif+SC:wght@${weight}&display=swap"
  ttf_url=$(curl -fsSL -A "${UA}" "${css_url}" | grep -oP "(?<=url\()https://[^)]+\.ttf" | head -1)
  [ -n "${ttf_url}" ] && download_ttf "NotoSerifSC-w${weight}.ttf" "${ttf_url}" || \
    echo "[warn] Could not resolve Noto Serif SC weight ${weight}"
done

[ -f "NotoSerifSC-w400.ttf" ] && cp "NotoSerifSC-w400.ttf" "NotoSerifSC-Regular.ttf"
[ -f "NotoSerifSC-w600.ttf" ] && cp "NotoSerifSC-w600.ttf" "NotoSerifSC-SemiBold.ttf"
[ -f "NotoSerifSC-w700.ttf" ] && cp "NotoSerifSC-w700.ttf" "NotoSerifSC-Bold.ttf"

# ── ZCOOL KuaiLe（快乐体，派对/打卡用）───────────────────────────────────────
css_url="${API}?family=ZCOOL+KuaiLe&display=swap"
ttf_url=$(curl -fsSL -A "${UA}" "${css_url}" | grep -oP "(?<=url\()https://[^)]+\.ttf" | head -1)
[ -n "${ttf_url}" ] && download_ttf "ZCOOLKuaiLe-Regular.ttf" "${ttf_url}" || \
  echo "[warn] Could not resolve ZCOOL KuaiLe"

# ── ZCOOL QingKe HuangYou（庆科黄油体，网红标题用）──────────────────────────
css_url="${API}?family=ZCOOL+QingKe+HuangYou&display=swap"
ttf_url=$(curl -fsSL -A "${UA}" "${css_url}" | grep -oP "(?<=url\()https://[^)]+\.ttf" | head -1)
[ -n "${ttf_url}" ] && download_ttf "ZCOOLQingKeHuangYou-Regular.ttf" "${ttf_url}" || \
  echo "[warn] Could not resolve ZCOOL QingKe HuangYou"

# ── Ma Shan Zheng（马山正楷，文艺气质用）─────────────────────────────────────
css_url="${API}?family=Ma+Shan+Zheng&display=swap"
ttf_url=$(curl -fsSL -A "${UA}" "${css_url}" | grep -oP "(?<=url\()https://[^)]+\.ttf" | head -1)
[ -n "${ttf_url}" ] && download_ttf "MaShanZheng-Regular.ttf" "${ttf_url}" || \
  echo "[warn] Could not resolve Ma Shan Zheng"

echo ""
echo "Done. Files in ${FONTS_DIR}:"
ls -lh "${FONTS_DIR}"/*.ttf 2>/dev/null || echo "  (no .ttf files found)"
