#!/usr/bin/env bash
# =============================================================================
# VidHarbor (影坞) 一键部署脚本 — Linux / macOS / WSL / Git Bash
#
# 用法:
#   ./deploy.sh              # 部署/启动（含 Evil0ctal 兜底栈 + GPU 自动探测）
#   ./deploy.sh up           # 同上
#   ./deploy.sh logs         # 查看日志（-f 跟随）
#   ./deploy.sh status       # 查看运行状态（含 Evil0ctal）
#   ./deploy.sh update       # git pull + 重建镜像并重启
#   ./deploy.sh restart      # 重启
#   ./deploy.sh backup       # 停止→打包 data/ library/ 到 backup/→重启
#   ./deploy.sh down         # 停止并移除容器（含 Evil0ctal）
#   ./deploy.sh buildx <registry/namespace/vidharbor:tag>
#                            # 构建并推送多架构镜像（linux/amd64 + linux/arm64）
#
# .env 可调项（首次运行自动生成）:
#   PORT=8666                # VidHarbor 宿主端口
#   TZ=Asia/Shanghai         # 容器时区
#   GPU=auto                 # 硬件转码: auto / nvidia / intel / cpu
#   WITH_EVIL0CTAL=1         # 是否随脚本部署 Evil0ctal 兜底服务（0 = 关闭）
#   EVIL0CTAL_API_KEY=       # 一般留空：脚本会自动创建并同步 Key；手动填写则视为手动管理
#   PROXY=                   # 出口代理（如 http://host.docker.internal:7890；留空=不用）
#   PROXY_PLATFORMS=         # 走代理的平台，JSON 数组（如 ["youtube","tiktok"]；设置页可覆盖）
# =============================================================================
set -euo pipefail

APP_NAME="VidHarbor"
COMPOSE_FILE="docker-compose.yml"
DEFAULT_PORT=8666
DTK_DIR="tools/dtk"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ---------------------------------------------------------------- 输出工具 ---
info()  { printf '\033[1;32m[INFO]\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m[WARN]\033[0m %s\n' "$*" >&2; }
error() { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; }
die()   { error "$*"; exit 1; }

os_kind() {
  case "$(uname -s)" in
    Linux*)  [[ -f /proc/version ]] && grep -qi microsoft /proc/version && echo "wsl" || echo "linux" ;;
    Darwin*) echo "macos" ;;
    MINGW*|MSYS*|CYGWIN*) echo "gitbash" ;;
    *) echo "unknown" ;;
  esac
}

# ------------------------------------------------------------ Docker 检查 ---
ensure_docker() {
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    return 0
  fi

  if command -v docker >/dev/null 2>&1; then
    die "检测到 docker 命令但守护进程未运行，请先启动 Docker（Linux: sudo systemctl start docker；Docker Desktop 请打开应用）"
  fi

  local kind; kind="$(os_kind)"
  case "$kind" in
    linux|wsl)
      info "未检测到 Docker，可以自动安装（官方 get.docker.com 脚本，需要 root/sudo）"
      local reply="n"
      if [[ -t 0 ]]; then
        read -r -p "现在安装 Docker? [y/N] " reply || true
      fi
      if [[ "${reply#[Yy]}" != "$reply" ]]; then
        local sudo_cmd=""
        [[ $EUID -ne 0 ]] && sudo_cmd="sudo"
        if command -v curl >/dev/null 2>&1; then
          curl -fsSL https://get.docker.com | $sudo_cmd sh
        else
          wget -qO- https://get.docker.com | $sudo_cmd sh
        fi
        $sudo_cmd systemctl enable --now docker 2>/dev/null || true
        # WSL + Docker Desktop 集成场景：安装后守护进程可能在 Windows 侧
        command -v docker >/dev/null 2>&1 || die "Docker 安装失败，请手动安装: https://docs.docker.com/engine/install/"
        docker info >/dev/null 2>&1 || die "Docker 已安装但守护进程未运行（WSL 请确认 Docker Desktop 的 WSL 集成已开启）"
        info "Docker 安装完成: $(docker --version)"
      else
        die "请先安装 Docker: https://docs.docker.com/engine/install/"
      fi
      ;;
    macos)
      die "未检测到 Docker。请安装 Docker Desktop（brew install --cask docker 或 https://docker.com）后重试"
      ;;
    gitbash)
      die "未检测到 Docker。请安装 Docker Desktop: winget install -e --id Docker.DockerDesktop （或 https://docker.com）后重试"
      ;;
    *)
      die "未检测到 Docker，请手动安装: https://docs.docker.com/engine/install/"
      ;;
  esac
}

# Compose v2 优先（docker compose），回退 docker-compose v1
compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    die "未检测到 Docker Compose。Docker Desktop 自带；Linux 请安装 compose 插件: apt install docker-compose-plugin"
  fi
}

# ------------------------------------------------------------------- .env ---
env_val() {
  local key="$1" def="${2:-}" val file="${3:-.env}"
  val="$(sed -n "s/^${key}=//p" "$file" 2>/dev/null | tail -1 | tr -d '\r' || true)"
  printf '%s' "${val:-$def}"
}

ensure_env() {
  if [[ ! -f "$COMPOSE_FILE" ]]; then
    die "未找到 $COMPOSE_FILE —— 请在仓库根目录运行本脚本"
  fi
  if [[ ! -f .env ]]; then
    cat > .env <<EOF
# VidHarbor Docker 部署配置（docker-compose.yml 读取，deploy.sh 也会补全缺失项）
# 宿主机访问端口
PORT=$DEFAULT_PORT
# 容器时区（影响日志与界面时间显示；定时任务时区在设置页配置）
TZ=Asia/Shanghai
# GPU 硬件转码: auto(自动探测) / nvidia / intel / cpu
GPU=auto
# 是否随脚本部署 Evil0ctal 兜底服务（抖音/TikTok；磁盘约 5GB，首次构建约 10 分钟）
WITH_EVIL0CTAL=1
# 一般留空：部署脚本会自动完成向导、创建并同步 API Key；手动填写则视为手动管理
EVIL0CTAL_API_KEY=
# 出口代理（只对 PROXY_PLATFORMS 列出的平台生效；留空=不用；设置页可覆盖）
# 宿主机代理在容器内的地址形如 http://host.docker.internal:7890
PROXY=
# 走代理的平台（JSON 数组）：["youtube","tiktok","bilibili","douyin"] 任选
PROXY_PLATFORMS=
# 可选访问令牌：设置后所有 API 需带令牌（浏览器首次访问 http://<host>:<port>/?token=<令牌>）
TOKEN=
# 端口绑定的网卡地址：默认 0.0.0.0（局域网可访问）；仅本机访问设 127.0.0.1
BIND_IP=0.0.0.0
EOF
    info "已生成 .env（可编辑 PORT/TZ/GPU/WITH_EVIL0CTAL 后重新 ./deploy.sh up）"
  fi
  # 旧版 .env 缺失的键自动补全
  grep -q '^PORT=' .env              || echo "PORT=$DEFAULT_PORT" >> .env
  grep -q '^TZ=' .env                || echo "TZ=Asia/Shanghai" >> .env
  grep -q '^GPU=' .env               || echo "GPU=auto" >> .env
  grep -q '^WITH_EVIL0CTAL=' .env    || echo "WITH_EVIL0CTAL=1" >> .env
  grep -q '^EVIL0CTAL_API_KEY=' .env || echo "EVIL0CTAL_API_KEY=" >> .env
  grep -q '^PROXY=' .env           || echo "PROXY=" >> .env
  grep -q '^PROXY_PLATFORMS=' .env || echo "PROXY_PLATFORMS=" >> .env
  grep -q '^TOKEN=' .env           || echo "TOKEN=" >> .env
  grep -q '^BIND_IP=' .env         || echo "BIND_IP=0.0.0.0" >> .env
}

current_port() { env_val PORT "$DEFAULT_PORT"; }

# ------------------------------------------------------- GPU 与 compose 组合 ---
docker_has_nvidia_runtime() {
  docker info 2>/dev/null | grep -qi nvidia
}

detect_gpu() {
  if command -v nvidia-smi >/dev/null 2>&1 && docker_has_nvidia_runtime; then
    # 仅原生 Linux 宿主机自动启用：WSL2/Docker Desktop 的 GPU 直通只含 CUDA，
    # 不含视频编码器（NVENC），硬件转码无法工作
    if [[ "$(os_kind)" == "linux" ]]; then
      echo "nvidia"; return
    fi
    warn "检测到 NVIDIA，但 WSL2/Docker Desktop 不直通视频编码器（NVENC），自动模式下使用 CPU 转码（Linux 宿主机可完整启用，或强制 GPU=nvidia）"
  fi
  if [[ -e /dev/dri ]]; then
    echo "intel"; return
  fi
  echo "cpu"
}

# 根据 .env 与探测结果维护 COMPOSE_FILE（Windows 用 ; 分隔，其余平台用 :）
write_compose_file() {
  local use_dtk="${1:-1}" sep files=() gpu line
  sep=":"
  [[ "$(os_kind)" == "gitbash" ]] && sep=";"
  files=("$COMPOSE_FILE")
  [[ "$use_dtk" == "1" ]] && files+=("docker-compose.evil0ctal.yml")
  gpu="$(env_val GPU auto)"
  [[ "$gpu" == "auto" ]] && gpu="$(detect_gpu)"
  case "$gpu" in
    nvidia)
      if docker_has_nvidia_runtime; then
        files+=("docker-compose.gpu-nvidia.yml")
      else
        warn "GPU=nvidia 但 Docker 缺少 nvidia 运行时，本次不启用 GPU 直通"
      fi
      ;;
    intel) files+=("docker-compose.gpu-intel.yml") ;;
    cpu)   ;;
    *)     warn "未知 GPU 值: $gpu（可选 auto/nvidia/intel/cpu），按 cpu 处理" ;;
  esac
  info "GPU 转码: $gpu | Evil0ctal 集成: $([[ $use_dtk == 1 ]] && echo 开 || echo 关)"
  line="$(IFS="$sep"; echo "${files[*]}")"
  if grep -q '^COMPOSE_FILE=' .env 2>/dev/null; then
    sed -i.bak "s|^COMPOSE_FILE=.*|COMPOSE_FILE=$line|" .env && rm -f .env.bak
  else
    printf '\n# 由 deploy.sh 自动维护（override 文件组合）\nCOMPOSE_FILE=%s\n' "$line" >> .env
  fi
}

# -------------------------------------------------------- Evil0ctal (dtk) ---
rand_hex() {
  if command -v openssl >/dev/null 2>&1; then openssl rand -hex "$1"
  else od -An -N"$1" -tx1 /dev/urandom | tr -d ' \n'; fi
}
rand_b64() {
  if command -v openssl >/dev/null 2>&1; then openssl rand -base64 "$1"
  else head -c "$1" /dev/urandom | base64; fi
}

dtk_compose() {
  ( cd "$DTK_DIR" && COMPOSE_ENV_FILES=.env docker compose -p dtk -f docker/compose.yml "$@" )
}

ensure_dtk() {
  command -v git >/dev/null 2>&1 || { warn "未找到 git —— 跳过 Evil0ctal 部署"; return 1; }
  if [[ ! -d "$DTK_DIR/.git" ]]; then
    info "克隆 Evil0ctal (Douyin_TikTok_Download_API v5) → $DTK_DIR ..."
    mkdir -p tools
    git clone --depth 1 https://github.com/Evil0ctal/Douyin_TikTok_Download_API.git "$DTK_DIR" \
      || { warn "克隆失败 —— 跳过 Evil0ctal 部署"; return 1; }
  fi
  if [[ ! -f "$DTK_DIR/.env" ]]; then
    local pg pw
    pg="$(rand_hex 24)"; pw="$(rand_hex 24)"
    cat > "$DTK_DIR/.env" <<EOF
# 由 deploy.sh 生成 —— 请备份；DTK_SECRET_KEY 丢失后已存 cookies/凭据将无法解密
# 使用 Docker Hub 预构建镜像（amd64/arm64）；固定版本改 DTK_IMAGE_TAG（如 5.1.6）
DTK_IMAGE=evil0ctal/douyin_tiktok_download_api
DTK_IMAGE_TAG=latest
DTK_SECRET_KEY=$(rand_b64 48)
POSTGRES_PASSWORD=$pg
REDIS_PASSWORD=$pw
DTK_DATABASE_URL=postgresql+asyncpg://dtk:$pg@postgres:5432/dtk
DTK_REDIS_URL=redis://:$pw@redis:6379/0
# 浏览器容器（抖音/TikTok 身份铸造必需）的 RPC 地址
DTK_BROWSER_RPC_URL=http://browser-rpc:9000
EOF
    info "已生成 $DTK_DIR/.env（随机密钥）"
  fi
  # VidHarbor 与 dtk 共用的外部网络（compose 文件里声明为 external）
  docker network create dtk_edge >/dev/null 2>&1 || true
  info "启动 Evil0ctal 栈（api/postgres/redis 拉预构建镜像，浏览器容器本地构建；首次约 10 分钟）..."
  if dtk_compose --profile browser up -d --build --wait --wait-timeout 300; then
    touch "$DTK_DIR/.deploy-ok"
    dtk_setup_hint
    return 0
  fi
  if [[ -f "$DTK_DIR/.deploy-ok" ]]; then
    warn "Evil0ctal 启动失败（已有历史成功部署，不重置其数据卷）；可稍后重试 ./deploy.sh up"
    return 1
  fi
  # 首次部署即失败：常见于 postgres 初始化竞态，重置数据卷（此时无用户数据）重试一次
  warn "首次启动失败 —— 重置 Evil0ctal 数据卷后自动重试一次..."
  dtk_compose down -v >/dev/null 2>&1 || true
  if dtk_compose --profile browser up -d --build --wait --wait-timeout 300; then
    touch "$DTK_DIR/.deploy-ok"
    dtk_setup_hint
    return 0
  fi
  warn "Evil0ctal 启动失败 —— VidHarbor 继续部署，可稍后重试 ./deploy.sh up"
  return 1
}

dtk_setup_hint() {
  echo
  info "Evil0ctal 控制台: http://127.0.0.1:8000（管理员账号密码见 $DTK_DIR/.env；服务器上建议 SSH 隧道访问）"
}

dtk_down() {
  [[ -d "$DTK_DIR/docker" ]] || return 0
  info "停止 Evil0ctal ..."
  # 必须带 --profile browser：compose 只清理当前启用 profile 的服务，否则浏览器容器会残留
  dtk_compose --profile browser down --remove-orphans || warn "Evil0ctal 停止失败（可忽略）"
}

# —— Evil0ctal 首次向导 + API Key 全自动配置（无需打开控制台手工操作）——
# 结果写入全局变量 DTK_API_KEY（为空即失败）；日志走 stdout，不能靠命令替换取值
ensure_dtk_apikey() {
  DTK_API_KEY=""
  local api="http://127.0.0.1:8000" cookies="$DTK_DIR/.cookies" user pass token status key
  # 管理员凭据：生成一次即存 .env（与栈内其他密钥同级）
  user="$(env_val DTK_ADMIN_USER vidharbor '' "$DTK_DIR/.env")"
  pass="$(env_val DTK_ADMIN_PASSWORD '' "$DTK_DIR/.env")"
  if [[ -z "$pass" ]]; then
    pass="$(rand_hex 12)"
    { printf 'DTK_ADMIN_USER=%s\n' "$user"; printf 'DTK_ADMIN_PASSWORD=%s\n' "$pass"; } >> "$DTK_DIR/.env"
    chmod 600 "$DTK_DIR/.env"
  fi
  status="$(curl -sf "$api/api/setup/status" 2>/dev/null || true)"
  if [[ "$status" != *'"initialized":true'* ]]; then
    token="$( (cd "$DTK_DIR" && COMPOSE_ENV_FILES=.env docker compose -p dtk -f docker/compose.yml logs api 2>/dev/null) \
      | grep -oE 'token=[A-Za-z0-9._-]+' | tail -1 | cut -d= -f2 || true)"
    if [[ -z "$token" ]]; then
      warn "未取得 Evil0ctal setup token，跳过 API Key 自动配置"
      return 1
    fi
    if ! curl -sf -X POST "$api/api/setup/init" -H 'content-type: application/json' \
         -d "{\"token\":\"$token\",\"username\":\"$user\",\"password\":\"$pass\"}" 2>/dev/null | grep -q '"username"'; then
      warn "Evil0ctal 管理员初始化失败（可能已被人工完成过向导，密码非脚本生成）——跳过 API Key 自动配置"
      return 1
    fi
    info "已自动创建 Evil0ctal 管理员（用户名 $user，密码在 $DTK_DIR/.env）"
  fi
  key="$(env_val DTK_VIDHARBOR_KEY '' "$DTK_DIR/.env")"
  if [[ -n "$key" ]]; then
    DTK_API_KEY="$key"
    return 0
  fi
  rm -f "$cookies"
  if ! curl -sf -c "$cookies" -X POST "$api/api/v1/auth/login" -H 'content-type: application/json' \
       -d "{\"username\":\"$user\",\"password\":\"$pass\"}" 2>/dev/null | grep -q '"username"'; then
    warn "登录 Evil0ctal 控制台失败 —— 跳过 API Key 自动配置（可稍后手动在控制台创建）"
    return 1
  fi
  key="$(curl -sf -b "$cookies" -X POST "$api/api/v1/admin/api-keys" -H 'content-type: application/json' \
       -d '{"name":"vidharbor","scopes":["douyin:read","tiktok:read"]}' 2>/dev/null \
       | grep -oE '"key": *"[^"]+"' | head -1 | sed 's/.*: *"//;s/"$//')"
  if [[ -z "$key" ]]; then
    warn "创建 Evil0ctal API Key 失败"
    return 1
  fi
  printf 'DTK_VIDHARBOR_KEY=%s\n' "$key" >> "$DTK_DIR/.env"
  chmod 600 "$DTK_DIR/.env"
  info "已创建 Evil0ctal API Key（douyin:read + tiktok:read）并自动写入 VidHarbor 设置"
  DTK_API_KEY="$key"
}

# 同步兜底引擎设置到 VidHarbor（地址 → 容器网络；API Key → 自动创建的那把；仅在有差异时写入）
sync_evil0ctal_settings() {
  local port="$1" key="${2:-}" cur cur_url cur_key payload i
  cur=""
  for i in 1 2 3 4 5 6; do
    cur="$(curl -sf "http://127.0.0.1:${port}/api/settings" 2>/dev/null || true)"
    [[ -n "$cur" ]] && break
    sleep 5
  done
  [[ -n "$cur" ]] || { warn "VidHarbor API 未就绪，跳过兜底引擎同步"; return 0; }
  cur_url="$(printf '%s' "$cur" | grep -o '"base_url": *"[^"]*"' | head -1 | sed 's/.*: *"//;s/"$//')"
  # settings JSON 中第一个 api_key 字段属于 evil0ctal（download/library 段没有）
  cur_key="$(printf '%s' "$cur" | grep -o '"api_key": *"[^"]*"' | head -1 | sed 's/.*: *"//;s/"$//')"
  # 用户在 .env 手动指定 EVIL0CTAL_API_KEY 时视为手动管理，自动同步不覆盖 key
  [[ -n "$(env_val EVIL0CTAL_API_KEY '')" ]] && key=""
  payload=""
  [[ "$cur_url" == "http://api:8000" ]] || payload='"base_url":"http://api:8000"'
  if [[ -n "$key" && "$cur_key" != "$key" ]]; then
    payload="${payload:+$payload,}\"api_key\":\"$key\""
  fi
  [[ -n "$payload" ]] || return 0
  if curl -sf -X PUT "http://127.0.0.1:${port}/api/settings" -H 'content-type: application/json' \
       -d "{\"evil0ctal\":{$payload}}" >/dev/null 2>&1; then
    info "兜底引擎设置已同步（地址=http://api:8000${key:+，API Key 已更新}，约 1 分钟内生效）"
  fi
}

# ---------------------------------------------------------------- 命令 ---
cmd_up() {
  ensure_docker
  ensure_env
  local use_dtk=1
  [[ "$(env_val WITH_EVIL0CTAL 1)" == "1" ]] || use_dtk=0
  if [[ $use_dtk -eq 1 ]]; then
    if ensure_dtk; then
      ensure_dtk_apikey
    elif ! docker network inspect dtk_edge >/dev/null 2>&1; then
      warn "Evil0ctal 未就绪且共享网络 dtk_edge 不存在 —— 本次以独立模式启动"
      use_dtk=0
    fi
  fi
  write_compose_file "$use_dtk"
  info "构建并启动 $APP_NAME（首次构建需数分钟：npm + ffmpeg + Python 依赖）..."
  compose up -d --build
  [[ "$use_dtk" == "1" ]] && sync_evil0ctal_settings "$(current_port)" "${DTK_API_KEY:-}"
  info "启动完成: http://127.0.0.1:$(current_port)  （数据保存在 ./data 与 ./library）"
  compose ps
}

cmd_down() {
  ensure_docker
  compose down
  dtk_down
  info "已停止"
}
cmd_restart(){ ensure_docker; compose restart && compose ps; }
cmd_status() {
  ensure_docker
  compose ps
  if [[ -d "$DTK_DIR/docker" ]]; then
    echo "--- Evil0ctal ---"
    ( cd "$DTK_DIR" && COMPOSE_ENV_FILES=.env docker compose -p dtk -f docker/compose.yml --profile browser ps ) || true
  fi
}

cmd_logs() {
  ensure_docker
  if [[ "${1:-}" == "-f" || "${1:-}" == "--follow" ]]; then
    compose logs -f
  else
    compose logs --tail=200
  fi
}

cmd_update() {
  ensure_docker
  ensure_env
  if [[ -d .git ]] && command -v git >/dev/null 2>&1; then
    info "拉取最新代码..."
    git pull --ff-only || warn "git pull 失败（可能有本地改动），使用当前代码继续"
  fi
  if [[ -d "$DTK_DIR/.git" ]]; then
    info "拉取 Evil0ctal 最新代码..."
    ( cd "$DTK_DIR" && git pull --ff-only ) || warn "Evil0ctal git pull 失败，使用当前代码继续"
  fi
  info "重建镜像并重启..."
  cmd_up
}

cmd_backup() {
  ensure_docker
  local stamp dest
  stamp="$(date +%Y%m%d-%H%M%S)"
  mkdir -p backup
  dest="backup/vidharbor-${stamp}.tar.gz"
  info "停止 VidHarbor 以保证 SQLite 备份一致性（Evil0ctal 不受影响）..."
  compose stop
  if tar --exclude='library/.tmp' -czf "$dest" data library; then
    info "已备份: $dest ($(du -h "$dest" | cut -f1))"
    info "恢复方法: tar -xzf $dest （在仓库根目录、服务停止时解压）"
  else
    error "备份失败"
  fi
  compose start
}

cmd_buildx() {
  ensure_docker
  local ref="${1:-}"
  [[ -z "$ref" ]] && die "用法: ./deploy.sh buildx <registry/namespace/vidharbor:tag>   例: ghcr.io/you/vidharbor:latest"
  docker buildx version >/dev/null 2>&1 || die "需要 buildx: https://github.com/docker/buildx#installing"
  info "构建并推送多架构镜像 linux/amd64,linux/arm64 → $ref ..."
  docker buildx build --platform linux/amd64,linux/arm64 -t "$ref" --push .
}

cmd_help() {
  local end
  end="$(grep -n '^# ====' "$0" | sed -n 2p | cut -d: -f1)"
  sed -n "2,${end}p" "$0" | sed 's/^# \{0,1\}//'
}

case "${1:-up}" in
  up)       shift 2>/dev/null || true; cmd_up "$@" ;;
  down)     cmd_down ;;
  restart)  cmd_restart ;;
  status)   cmd_status ;;
  logs)     shift 2>/dev/null || true; cmd_logs "$@" ;;
  update)   cmd_update ;;
  backup)   cmd_backup ;;
  buildx)   shift; cmd_buildx "$@" ;;
  help|-h|--help) cmd_help ;;
  *) die "未知命令: $1（./deploy.sh help 查看用法）" ;;
esac
