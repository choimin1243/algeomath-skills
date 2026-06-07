# -*- coding: utf-8 -*-
"""
algeomath MCP 서버 v2
- algeo2d              : AlgeoMath 2D 도형 추가 (브라우저 실시간 반영)
- algeo2d_screenshot   : AlgeoMath 2D 스크린샷
- stackblocks          : AlgeoMath 3D 쌓기나무 (브라우저 실시간 반영 + 터미널 뷰)
- stackblocks_screenshot: AlgeoMath 3D 스크린샷
"""
import sys, json, asyncio, io, re, copy
from pathlib import Path
from contextlib import redirect_stdout
from mcp.server.fastmcp import FastMCP
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
from algeo2d import Scene, parse_floats, DEFAULT_PT, DEFAULT_SEG, DEFAULT_PLY
from stackblocks import Grid, cmd as sb_cmd, view_all

mcp = FastMCP("algeomath")

# ── 공유 상태 ─────────────────────────────────────────────────
# 2D
_pw_2d = _browser_2d = _page_2d = _frame_2d = None
_lock_2d: asyncio.Lock | None = None

# 3D
_pw_3d = _browser_3d = _page_3d = _frame_3d = None
_lock_3d: asyncio.Lock | None = None
_scene_3d_template: dict | None = None  # 빈 씬 캐시 (최초 1회만 저장)
_grid = Grid(5, 5, 5)

COLORS_3D = {1: 0x81C784, 2: 0xFF8F00, 3: 0xE53935, 4: 0x1565C0, 5: 0x7B1FA2}
ANSI = re.compile(r'\033\[[0-9;]*m')
MUTATING = frozenset([
    '놓기','place','p','빼기','remove','r',
    '쌓기','stack','s','초기화','clear',
    '되돌리기','undo','u','불러오기','load',
])


def _strip(s: str) -> str:
    return ANSI.sub('', s)


# asyncio.Lock은 이벤트 루프 안에서 lazy 생성
def _lock2d() -> asyncio.Lock:
    global _lock_2d
    if _lock_2d is None:
        _lock_2d = asyncio.Lock()
    return _lock_2d


def _lock3d() -> asyncio.Lock:
    global _lock_3d
    if _lock_3d is None:
        _lock_3d = asyncio.Lock()
    return _lock_3d


# ── 2D 브라우저 관리 ──────────────────────────────────────────
async def _get_frame_2d():
    """AlgeoMath 2D 앱 iframe을 반환. 미연결 시 브라우저를 시작."""
    global _pw_2d, _browser_2d, _page_2d, _frame_2d
    async with _lock2d():
        if _frame_2d is not None:
            return _frame_2d
        _pw_2d = await async_playwright().start()
        _browser_2d = await _pw_2d.chromium.launch(
            headless=False, args=['--start-maximized']
        )
        _page_2d = await _browser_2d.new_page()
        await _page_2d.set_viewport_size({'width': 1400, 'height': 900})
        await _page_2d.goto('https://www.algeomath.kr/kids/algeomath/app/make')
        # 고정 sleep 대신 algeoApp 준비까지 폴링 (최대 15초)
        for _ in range(30):
            for f in _page_2d.frames:
                if 'tools/app' not in f.url:
                    continue
                try:
                    if await f.evaluate('() => typeof window.algeoApp !== "undefined"'):
                        _frame_2d = f
                        break
                except Exception:
                    pass
            if _frame_2d:
                break
            await asyncio.sleep(0.5)
        if _frame_2d is None:
            raise RuntimeError("AlgeoMath 2D 앱 프레임을 찾을 수 없습니다.")
    return _frame_2d


# ── 3D 브라우저 관리 ──────────────────────────────────────────
async def _get_frame_3d():
    """AlgeoMath 3D 앱 frame을 반환. 미연결 시 브라우저를 시작."""
    global _pw_3d, _browser_3d, _page_3d, _frame_3d, _scene_3d_template
    async with _lock3d():
        if _frame_3d is not None:
            return _frame_3d
        _pw_3d = await async_playwright().start()
        _browser_3d = await _pw_3d.chromium.launch(
            headless=False, args=['--start-maximized']
        )
        _page_3d = await _browser_3d.new_page()
        await _page_3d.set_viewport_size({'width': 1400, 'height': 900})
        await _page_3d.goto('https://www.algeomath.kr/kids/algeomath/poly/make')
        # AlgeomathPoly API 준비까지 폴링 (최대 15초)
        for _ in range(30):
            for f in _page_3d.frames:
                try:
                    if await f.evaluate('() => typeof window.AlgeomathPoly !== "undefined"'):
                        _frame_3d = f
                        break
                except Exception:
                    pass
            if _frame_3d:
                break
            await asyncio.sleep(0.5)
        if _frame_3d is None:
            raise RuntimeError("AlgeoMath 3D API를 찾을 수 없습니다.")
        # 빈 씬 템플릿 1회 캐시 (이후 deep copy로 재사용)
        raw = await _frame_3d.evaluate(
            '() => JSON.stringify(window.AlgeomathPoly.api.save())'
        )
        _scene_3d_template = json.loads(raw)
    return _frame_3d


# ── 2D 주입 / 씬 읽기 ────────────────────────────────────────
async def _inject_2d(frame, scene: Scene) -> None:
    js = json.dumps(scene.to_json_str())
    await frame.evaluate(f'''() => {{
        const compressed = "v1_" + LZString.compressToEncodedURIComponent({js});
        window.algeoApp.load(compressed);
    }}''')


async def _get_scene_2d(frame) -> Scene | None:
    decoded = await frame.evaluate('''() => {
        const s = window.algeoApp.save();
        if (!s) return null;
        let d = s.startsWith("v1_") ? s.slice(3) : s;
        return LZString.decompressFromEncodedURIComponent(d);
    }''')
    return Scene(json.loads(decoded)) if decoded else None


# ── 3D 주입 ──────────────────────────────────────────────────
async def _inject_3d(frame, grid: Grid) -> int:
    """Grid 상태를 AlgeoMath 3D에 주입. 반환: 주입된 블록 수."""
    base = copy.deepcopy(_scene_3d_template)
    blocks = [
        {
            'id': 100 + i,
            'typeName': 'STACK_CUBE',
            'name': 'stackCube',
            'is2DObject': False,
            'color': COLORS_3D.get(z, 0xFFFFFF),
            'measurementType': None,
            'visible': True,
            'position': {'x': (x-1) + 0.5, 'y': -((y-1) + 0.5), 'z': z - 0.5},
            'rotation': {'_x': 0, '_y': 0, '_z': 0, '_order': 'XYZ'},
            'scale': {'x': 1, 'y': 1, 'z': 1},
        }
        for i, (x, y, z) in enumerate(sorted(grid.blocks))
    ]
    base['scene']['objectDatas'] = blocks
    await frame.evaluate('(d) => window.AlgeomathPoly.api.load(d)', base)
    return len(blocks)


# ── algeo2d 도구 (2D) ────────────────────────────────────────
@mcp.tool()
async def algeo2d(command: str) -> str:
    """AlgeoMath 2D에 도형을 추가하거나 초기화합니다.

    command 문법 (수학 좌표계):
      점 x y [색상]
      선분 x1 y1 x2 y2 [색상]
      삼각형 x1 y1 x2 y2 x3 y3 [색상]
      사각형 x y 가로 세로 [색상]
      사각형 x1 y1 x2 y2 x3 y3 x4 y4 [색상]
      다각형 x1 y1 x2 y2 ... [색상]
      원 cx cy r [색상]
      초기화

    색상 옵션: blue red green orange purple cyan
    예시: '삼각형 0 0 3 0 1.5 2.5 red'
    """
    toks = command.strip().split()
    if not toks:
        return "빈 명령어입니다."
    verb = toks[0].lower()

    if verb in ('도움말', 'help', 'h', '?'):
        return "점 x y | 선분 | 삼각형 | 사각형 | 다각형 | 원 cx cy r | 초기화"

    try:
        frame = await _get_frame_2d()
    except RuntimeError as e:
        return f"오류: {e}"

    if verb in ('초기화', 'clear', 'reset'):
        sc = await _get_scene_2d(frame)
        if sc:
            sc.data['objectCapsules'] = [
                o for o in sc.data['objectCapsules']
                if o['typeName'] == 'AxisSegment'
            ]
            await _inject_2d(frame, sc)
        return "초기화 완료"

    vals, color = parse_floats(toks[1:])
    sc = await _get_scene_2d(frame)
    if sc is None:
        return "오류: AlgeoMath 2D 씬을 읽을 수 없습니다."

    try:
        if verb in ('점', 'point', 'p'):
            if len(vals) < 2:
                return "사용법: 점 x y [색상]"
            sc.add_free_point(vals[0], vals[1], color=color or DEFAULT_PT)
            msg = f"점 ({vals[0]}, {vals[1]}) 추가"

        elif verb in ('선분', 'segment', 'seg'):
            if len(vals) < 4:
                return "사용법: 선분 x1 y1 x2 y2 [색상]"
            sc.add_segment(*vals[:4], color=color or DEFAULT_SEG)
            msg = f"선분 ({vals[0]},{vals[1]})→({vals[2]},{vals[3]}) 추가"

        elif verb in ('삼각형', 'triangle', 'tri'):
            if len(vals) < 6:
                return "사용법: 삼각형 x1 y1 x2 y2 x3 y3 [색상]"
            pts = [(vals[i], vals[i+1]) for i in range(0, 6, 2)]
            sc.add_polygon(pts, color=color or DEFAULT_PLY)
            msg = f"삼각형 {pts} 추가"

        elif verb in ('사각형', 'rect', 'rectangle'):
            if len(vals) >= 8:
                pts = [(vals[i], vals[i+1]) for i in range(0, 8, 2)]
            elif len(vals) == 4:
                x, y, w, h = vals
                pts = [(x, y), (x+w, y), (x+w, y+h), (x, y+h)]
            else:
                return "사용법: 사각형 x y 가로 세로 [색상]"
            sc.add_polygon(pts, color=color or DEFAULT_PLY)
            msg = "사각형 추가"

        elif verb in ('다각형', 'polygon', 'poly'):
            if len(vals) < 6 or len(vals) % 2 != 0:
                return "사용법: 다각형 x1 y1 x2 y2 ... (꼭짓점 3개 이상)"
            pts = [(vals[i], vals[i+1]) for i in range(0, len(vals), 2)]
            sc.add_polygon(pts, color=color or DEFAULT_PLY)
            msg = f"{len(pts)}각형 추가"

        elif verb in ('원', 'circle'):
            if len(vals) < 3:
                return "사용법: 원 cx cy r [색상]"
            sc.add_circle(vals[0], vals[1], vals[2], color=color or '#e53935')
            msg = f"원 중심({vals[0]},{vals[1]}) 반지름{vals[2]} 추가"

        else:
            return (
                f"알 수 없는 명령어: '{toks[0]}'\n"
                "사용 가능: 점 선분 삼각형 사각형 다각형 원 초기화"
            )

        await _inject_2d(frame, sc)
        return msg + " 완료"

    except Exception as e:
        return f"오류: {e}"


@mcp.tool()
async def algeo2d_screenshot(path: str = "C:/Users/choi2/algeo2d_shot.png") -> str:
    """AlgeoMath 2D 현재 화면을 스크린샷으로 저장합니다."""
    global _page_2d
    if _page_2d is None:
        try:
            await _get_frame_2d()
        except RuntimeError as e:
            return f"오류: {e}"
    await _page_2d.screenshot(path=path)
    return f"스크린샷 저장: {path}"


# ── stackblocks 도구 (3D) ─────────────────────────────────────
@mcp.tool()
async def stackblocks(command: str) -> str:
    """AlgeoMath 3D 쌓기나무 블록을 조작합니다 (브라우저 실시간 반영 + 터미널 뷰).

    command 예시:
      놓기 x y z       블록 1개 놓기  (place / p)
      빼기 x y z       블록 제거      (remove / r)
      쌓기 x y 높이    해당 열 채우기 (stack / s)
      보기             세 뷰 동시 표시
      위 / 앞 / 옆     개별 뷰
      층 N             N층 평면도
      3D               층별 3D 뷰
      개수             블록 수
      초기화           전체 삭제
      되돌리기         실행 취소

    좌표: x=가로(1=왼쪽), y=깊이(1=앞), z=높이(1=아래)  그리드: 5×5×5
    """
    first = command.strip().split()[0].lower() if command.strip() else ''

    if first in ('종료', 'quit', 'exit', 'q'):
        return "MCP 서버에서는 종료 명령을 사용할 수 없습니다."

    # 터미널 명령 실행 (Grid 상태 업데이트 + ASCII 뷰 생성)
    out = io.StringIO()
    with redirect_stdout(out):
        sb_cmd(_grid, command)
    result = _strip(out.getvalue()).strip()

    # 블록 변경 명령 → AlgeoMath 3D 브라우저에도 반영
    if first in MUTATING:
        try:
            frame = await _get_frame_3d()
            n = await _inject_3d(frame, _grid)
            result += f'\n[AlgeoMath 3D 반영: {n}블록]'
        except Exception as e:
            result += f'\n[3D 브라우저 오류: {e}]'

        # 3뷰 ASCII 자동 첨부
        view_out = io.StringIO()
        with redirect_stdout(view_out):
            for line in view_all(_grid):
                print(line)
        result += '\n\n' + _strip(view_out.getvalue())

    return result.strip() or "완료"


@mcp.tool()
async def stackblocks_screenshot(path: str = "C:/Users/choi2/algeo3d_shot.png") -> str:
    """AlgeoMath 3D 현재 화면을 스크린샷으로 저장합니다."""
    global _page_3d
    if _page_3d is None:
        try:
            await _get_frame_3d()
        except RuntimeError as e:
            return f"오류: {e}"
    await _page_3d.screenshot(path=path)
    return f"스크린샷 저장: {path}"


# ── 진입점 ──────────────────────────────────────────────────
if __name__ == '__main__':
    mcp.run()
