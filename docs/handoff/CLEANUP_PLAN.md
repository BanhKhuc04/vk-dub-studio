# Kế Hoạch Dọn Dẹp Cấu Trúc Kho Lưu Trữ (CLEANUP_PLAN.md)

**Mục tiêu**: Chuẩn hóa cấu trúc thư mục repo TOOLVIDEO / VK Dub Studio theo quy chuẩn Python project chuyên nghiệp, phân tách rõ ràng source code, scripts, specs, screenshots và archive logs, **tuyệt đối không làm hỏng khả năng chạy của ứng dụng hay các bộ kiểm thử tự động**.

---

## 1. Cấu Trúc Thư Mục Mới Đề Xuất (Target Layout)

```text
ToolVideo/
├── .agent/                             # Chuẩn Antigravity / Claude Code Skills
│   └── skills/
│       ├── kappak-ui-design/
│       └── toolvideo-dev/
├── .agents/
│   └── skills/                         # Backup workspace skills
├── .env.example                        # Mẫu biến môi trường (root)
├── .gitignore                          # Cấu hình bỏ qua git (root)
├── AGENTS.md                           # Quy chuẩn hoạt động Agent (root)
├── README.md                           # Giới thiệu dự án (root)
├── pyproject.toml                      # Cấu hình dự án & dependencies (root)
├── uv.lock                             # Khóa phiên bản uv (root)
├── app.py                              # Entrypoint chính của ứng dụng Python (root)
│
├── apps/                               # Các ứng dụng ngoại vi (browser-extension)
│   └── browser-extension/
│
├── src/                                # Toàn bộ Python source packages
│   ├── kappak/                         # Package KAPPAK Studio V2
│   └── vkdub/                          # Package VK Dub Studio Core
│
├── frontend/                           # Giao diện Web (React 19 + Vite)
│
├── scripts/                            # Toàn bộ script điều khiển (.bat, .ps1, test scripts)
│   ├── run_app.bat                     # Chạy Web Studio server
│   ├── run_kappak.bat                  # Chạy Desktop GUI Studio
│   ├── Chạy_VK_Dub_Studio.bat          # Click-to-run dành cho người dùng
│   ├── reload_extension.bat            # Reload & register browser extension
│   ├── dev.ps1
│   └── smoke_*.py
│
├── tools/                              # Binary ngoại vi & Native Messaging Host
│   ├── ffmpeg.exe                      # Binaries (được gitignore)
│   ├── ffprobe.exe
│   ├── yt-dlp/
│   └── native_host/                    # Giữ nguyên phục vụ Windows Registry browser host
│       ├── com.vkdub.bridge.json
│       ├── register_host.py
│       ├── vkdub_host.bat              # Host batch wrapper (Registry trỏ tới)
│       └── vkdub_host.py
│
├── resources/                          # Tài nguyên media, icons, logo
│   ├── test_icon.ico
│   ├── kappak/
│   └── icons/
│
├── packaging/                          # Cấu hình đóng gói & auto-updater
│   └── latest.json
│
├── tests/                              # Bộ kiểm thử Pytest tự động
│
├── docs/                               # Toàn bộ tài liệu dự án
│   ├── specs/                          # Toàn bộ file đặc tả kỹ thuật, kiến trúc & prompt
│   │   ├── VK_DUB_STUDIO_V2_SPEC.md
│   │   ├── VK_DUB_STUDIO_TOAN_BO_DU_AN.md
│   │   ├── UI_RESTRUCTURE_PLAN.md
│   │   ├── H6_ARCHITECTURE_RESET.md
│   │   ├── ORIGINAL_REQUEST.md
│   │   ├── CODEX_MASTER_PROMPT_VK_DUB_STUDIO.md
│   │   └── ANTIGRAVITY_V2_UPGRADE_PROMPT.md
│   ├── design_specs/                   # Thiết kế UI & target specs (Female Hero V2)
│   │   └── KAPPAK_UI_FemaleHero_AppleGlass_V2/
│   ├── screenshots/                    # Toàn bộ ảnh chụp màn hình UI hiện tại & lịch sử
│   │   ├── current_ui.png
│   │   ├── kappak_shell_phase0.png
│   │   ├── ui_*.png                    # Các dialog screenshots ở root
│   │   ├── before/
│   │   ├── dark/
│   │   └── wide_1920x1080/
│   ├── handoff/                        # Tài liệu bàn giao hiện hành
│   │   ├── PROGRESS.md
│   │   ├── STATUS.md
│   │   ├── CLEANUP_PLAN.md
│   │   ├── screenshots/                # Screenshots bàn giao V2 mới nhất
│   │   └── archive/                    # Lưu trữ log multi-agent cũ (.agents/teamwork_preview_*)
│   │       ├── sentinel/
│   │       └── teamwork_preview_*/
│   ├── evidence/                       # Bằng chứng kiểm thử runbook
│   └── research/
│
├── archive/                            # Kho lưu trữ file nén / release cũ (không phải source)
│   └── releases/
│       ├── VK_Dub_Studio_Ban_Day_Du_Nhe.zip
│       ├── KAPPAK_Extension_v2.3.0_Cai_Dat.zip
│       ├── kappak-ui-design-skill.zip
│       └── vbee-current-failure-diagnostic.zip
│
└── workspace/                          # Runtime workspace (gitignored, chỉ lưu data sinh ra khi chạy)
    └── cache/
```

---

## 2. Bảng Phân Loại Toàn Bộ File & Thư Mục

| Nhóm phân loại | Tên File / Thư Mục | Vị trí hiện tại | Hướng xử lý |
|---|---|---|---|
| **Source code** | `app.py` | Root | Giữ nguyên root |
| **Source code** | `src/` | Root | Giữ nguyên root |
| **Source code** | `frontend/` | Root | Giữ nguyên root |
| **Source code** | `apps/` | Root | Giữ nguyên root |
| **Source code** | `tests/` | Root | Giữ nguyên root |
| **Source code** | `vkdub/` | Root | Giữ nguyên root (package import) |
| **Source code / Host** | `tools/native_host/*` | `tools/native_host/` | Giữ nguyên vì Windows Registry Native Host gắn cứng đường dẫn |
| **Cấu hình** | `.env.example`, `pyproject.toml`, `uv.lock`, `README.md`, `AGENTS.md` | Root | Giữ nguyên root |
| **Cấu hình** | `.gitignore` | Root | Cập nhật thêm rules loại bỏ cache/artifacts |
| **Cấu hình** | `latest.json` | Root | Di chuyển sang `packaging/latest.json` |
| **Script chạy (.bat)** | `run_app.bat` | Root | Di chuyển sang `scripts/run_app.bat` |
| **Script chạy (.bat)** | `run_kappak.bat` | Root | Di chuyển sang `scripts/run_kappak.bat` |
| **Script chạy (.bat)** | `Chạy_VK_Dub_Studio.bat` | Root | Di chuyển sang `scripts/Chạy_VK_Dub_Studio.bat` |
| **Script chạy (.bat)** | `reload_extension.bat` | `tools/` | Di chuyển sang `scripts/reload_extension.bat` |
| **Tài liệu / Spec** | `VK_DUB_STUDIO_V2_SPEC.md` | Root | Di chuyển sang `docs/specs/` |
| **Tài liệu / Spec** | `VK_DUB_STUDIO_TOAN_BO_DU_AN.md` | Root | Di chuyển sang `docs/specs/` |
| **Tài liệu / Spec** | `UI_RESTRUCTURE_PLAN.md` | Root | Di chuyển sang `docs/specs/` |
| **Tài liệu / Spec** | `H6_ARCHITECTURE_RESET.md` | Root | Di chuyển sang `docs/specs/` |
| **Tài liệu / Spec** | `ORIGINAL_REQUEST.md` | Root | Di chuyển sang `docs/specs/` |
| **Tài liệu / Spec** | `CODEX_MASTER_PROMPT_VK_DUB_STUDIO.md` | Root | Di chuyển sang `docs/specs/` |
| **Tài liệu / Spec** | `ANTIGRAVITY_V2_UPGRADE_PROMPT.md` | Root | Di chuyển sang `docs/specs/` |
| **Tài liệu / Spec** | `KAPPAK_UI_FemaleHero_AppleGlass_V2` | Root | Di chuyển sang `docs/design_specs/` |
| **Ảnh minh hoạ UI** | `current_ui.png`, `kappak_shell_phase0.png`, `ui_*.png` (10 files) | Root | Di chuyển sang `docs/screenshots/` |
| **Ảnh minh hoạ UI** | `ui_screenshots/*` (`before/`, `dark/`, `wide_1920x1080/`, 20 files png) | `ui_screenshots/` | Di chuyển sang `docs/screenshots/` |
| **Asset / Resource** | `test_icon.ico` | Root | Di chuyển sang `resources/test_icon.ico` |
| **Skill Agent** | `kappak-ui-design`, `toolvideo-dev` | `.agent/skills/` | Giữ nguyên chuẩn Antigravity/Claude Code |
| **Log Multi-Agent cũ** | `sentinel/` | `.agents/` | Di chuyển sang `docs/handoff/archive/sentinel/` |
| **Log Multi-Agent cũ** | `teamwork_preview_*/` (29 thư mục) | `.agents/` | Di chuyển sang `docs/handoff/archive/` |
| **Log Multi-Agent cũ** | `.agents/ORIGINAL_REQUEST.md` | `.agents/` | Di chuyển sang `docs/handoff/archive/ORIGINAL_REQUEST.md` |
| **Archive / Backup** | `*.zip` (4 files tại root) | Root | Di chuyển sang `archive/releases/` |
| **Cache / Log tạm** | `app_launch.log`, `__pycache__` | Root & repo | Xóa bỏ khỏi git index, thêm vào `.gitignore` |

---

## 3. Bảng Chi Tiết: Đường Dẫn Cũ ➔ Đường Dẫn Mới

### 3.1. Nhóm Script Chạy (.bat) ➔ `scripts/`
| # | Đường dẫn cũ | Đường dẫn mới | Ghi chú tương thích |
|---|---|---|---|
| 1 | `run_app.bat` | `scripts/run_app.bat` | Cập nhật `cd /d "%~dp0.."` để trỏ về root khi chạy |
| 2 | `run_kappak.bat` | `scripts/run_kappak.bat` | Cập nhật `cd /d "%~dp0.."` để trỏ về root khi chạy |
| 3 | `Chạy_VK_Dub_Studio.bat` | `scripts/Chạy_VK_Dub_Studio.bat` | Cập nhật `cd /d "%~dp0.."` để trỏ về root khi chạy |
| 4 | `tools/reload_extension.bat` | `scripts/reload_extension.bat` | `%~dp0..` vẫn resolve chuẩn về root |

### 3.2. Nhóm Tài Liệu & Specs ➔ `docs/specs/`
| # | Đường dẫn cũ | Đường dẫn mới |
|---|---|---|
| 5 | `VK_DUB_STUDIO_V2_SPEC.md` | `docs/specs/VK_DUB_STUDIO_V2_SPEC.md` |
| 6 | `VK_DUB_STUDIO_TOAN_BO_DU_AN.md` | `docs/specs/VK_DUB_STUDIO_TOAN_BO_DU_AN.md` |
| 7 | `UI_RESTRUCTURE_PLAN.md` | `docs/specs/UI_RESTRUCTURE_PLAN.md` |
| 8 | `H6_ARCHITECTURE_RESET.md` | `docs/specs/H6_ARCHITECTURE_RESET.md` |
| 9 | `ORIGINAL_REQUEST.md` | `docs/specs/ORIGINAL_REQUEST.md` |
| 10 | `CODEX_MASTER_PROMPT_VK_DUB_STUDIO.md` | `docs/specs/CODEX_MASTER_PROMPT_VK_DUB_STUDIO.md` |
| 11 | `ANTIGRAVITY_V2_UPGRADE_PROMPT.md` | `docs/specs/ANTIGRAVITY_V2_UPGRADE_PROMPT.md` |
| 12 | `KAPPAK_UI_FemaleHero_AppleGlass_V2` | `docs/design_specs/KAPPAK_UI_FemaleHero_AppleGlass_V2` |

### 3.3. Nhóm Ảnh Minh Hoạ UI ➔ `docs/screenshots/`
| # | Đường dẫn cũ | Đường dẫn mới |
|---|---|---|
| 13 | `current_ui.png` | `docs/screenshots/current_ui.png` |
| 14 | `kappak_shell_phase0.png` | `docs/screenshots/kappak_shell_phase0.png` |
| 15 | `ui_export_dialog.png` | `docs/screenshots/ui_export_dialog.png` |
| 16 | `ui_log_viewer_dialog.png` | `docs/screenshots/ui_log_viewer_dialog.png` |
| 17 | `ui_main_window_phase6.png` | `docs/screenshots/ui_main_window_phase6.png` |
| 18 | `ui_main_window_phase7.png` | `docs/screenshots/ui_main_window_phase7.png` |
| 19 | `ui_main_window_phase8.png` | `docs/screenshots/ui_main_window_phase8.png` |
| 20 | `ui_mask_dialog.png` | `docs/screenshots/ui_mask_dialog.png` |
| 21 | `ui_settings_advanced_tab.png` | `docs/screenshots/ui_settings_advanced_tab.png` |
| 22 | `ui_settings_update_tab.png` | `docs/screenshots/ui_settings_update_tab.png` |
| 23 | `ui_subtitle_dialog.png` | `docs/screenshots/ui_subtitle_dialog.png` |
| 24 | `ui_update_dialog.png` | `docs/screenshots/ui_update_dialog.png` |
| 25 | `ui_screenshots/*` | `docs/screenshots/*` (bao gồm `before/`, `dark/`, `wide_1920x1080/`) |

### 3.4. Nhóm Log Multi-Agent Cũ ➔ `docs/handoff/archive/`
| # | Đường dẫn cũ | Đường dẫn mới |
|---|---|---|
| 26 | `.agents/sentinel/` | `docs/handoff/archive/sentinel/` |
| 27 | `.agents/teamwork_preview_auditor_1/` | `docs/handoff/archive/teamwork_preview_auditor_1/` |
| 28 | `.agents/teamwork_preview_auditor_m3_1/` | `docs/handoff/archive/teamwork_preview_auditor_m3_1/` |
| 29 | `.agents/teamwork_preview_challenger_1/` | `docs/handoff/archive/teamwork_preview_challenger_1/` |
| 30 | `.agents/teamwork_preview_challenger_2/` | `docs/handoff/archive/teamwork_preview_challenger_2/` |
| 31 | `.agents/teamwork_preview_challenger_m3_1/` | `docs/handoff/archive/teamwork_preview_challenger_m3_1/` |
| 32 | `.agents/teamwork_preview_explorer_survey_1/` | `docs/handoff/archive/teamwork_preview_explorer_survey_1/` |
| 33 | `.agents/teamwork_preview_explorer_survey_2/` | `docs/handoff/archive/teamwork_preview_explorer_survey_2/` |
| 34 | `.agents/teamwork_preview_explorer_survey_3/` | `docs/handoff/archive/teamwork_preview_explorer_survey_3/` |
| 35 | `.agents/teamwork_preview_explorer_survey_bridge/` | `docs/handoff/archive/teamwork_preview_explorer_survey_bridge/` |
| 36 | `.agents/teamwork_preview_explorer_survey_video/` | `docs/handoff/archive/teamwork_preview_explorer_survey_video/` |
| 37 | `.agents/teamwork_preview_orchestrator_1/` | `docs/handoff/archive/teamwork_preview_orchestrator_1/` |
| 38 | `.agents/teamwork_preview_orchestrator_2/` | `docs/handoff/archive/teamwork_preview_orchestrator_2/` |
| 39 | `.agents/teamwork_preview_reviewer_1/` | `docs/handoff/archive/teamwork_preview_reviewer_1/` |
| 40 | `.agents/teamwork_preview_reviewer_2/` | `docs/handoff/archive/teamwork_preview_reviewer_2/` |
| 41 | `.agents/teamwork_preview_reviewer_m1_1/` | `docs/handoff/archive/teamwork_preview_reviewer_m1_1/` |
| 42 | `.agents/teamwork_preview_reviewer_m3_1/` | `docs/handoff/archive/teamwork_preview_reviewer_m3_1/` |
| 43 | `.agents/teamwork_preview_reviewer_m3_2/` | `docs/handoff/archive/teamwork_preview_reviewer_m3_2/` |
| 44 | `.agents/teamwork_preview_spec_miner_survey_ext/` | `docs/handoff/archive/teamwork_preview_spec_miner_survey_ext/` |
| 45 | `.agents/teamwork_preview_test_writer_e2e/` | `docs/handoff/archive/teamwork_preview_test_writer_e2e/` |
| 46 | `.agents/teamwork_preview_victory_auditor_1/` | `docs/handoff/archive/teamwork_preview_victory_auditor_1/` |
| 47 | `.agents/teamwork_preview_worker_e2e_1/` | `docs/handoff/archive/teamwork_preview_worker_e2e_1/` |
| 48 | `.agents/teamwork_preview_worker_m1/` | `docs/handoff/archive/teamwork_preview_worker_m1/` |
| 49 | `.agents/teamwork_preview_worker_m1_1/` | `docs/handoff/archive/teamwork_preview_worker_m1_1/` |
| 50 | `.agents/teamwork_preview_worker_m2/` | `docs/handoff/archive/teamwork_preview_worker_m2/` |
| 51 | `.agents/teamwork_preview_worker_m2_1/` | `docs/handoff/archive/teamwork_preview_worker_m2_1/` |
| 52 | `.agents/teamwork_preview_worker_m3/` | `docs/handoff/archive/teamwork_preview_worker_m3/` |
| 53 | `.agents/teamwork_preview_worker_m3_fix_1/` | `docs/handoff/archive/teamwork_preview_worker_m3_fix_1/` |
| 54 | `.agents/teamwork_preview_worker_m4/` | `docs/handoff/archive/teamwork_preview_worker_m4/` |
| 55 | `.agents/teamwork_preview_worker_m5/` | `docs/handoff/archive/teamwork_preview_worker_m5/` |
| 56 | `.agents/ORIGINAL_REQUEST.md` | `docs/handoff/archive/ORIGINAL_REQUEST.md` |

### 3.5. Nhóm Archive Releases (.zip) ➔ `archive/releases/`
| # | Đường dẫn cũ | Đường dẫn mới |
|---|---|---|
| 57 | `VK_Dub_Studio_Ban_Day_Du_Nhe.zip` | `archive/releases/VK_Dub_Studio_Ban_Day_Du_Nhe.zip` |
| 58 | `KAPPAK_Extension_v2.3.0_Cai_Dat.zip` | `archive/releases/KAPPAK_Extension_v2.3.0_Cai_Dat.zip` |
| 59 | `kappak-ui-design-skill.zip` | `archive/releases/kappak-ui-design-skill.zip` |
| 60 | `vbee-current-failure-diagnostic.zip` | `archive/releases/vbee-current-failure-diagnostic.zip` |

### 3.6. Các File & Thư Mục Khác
| # | Tên file / Thư mục | Hành động | Ghi chú |
|---|---|---|---|
| 61 | `test_icon.ico` | Di chuyển sang `resources/test_icon.ico` | Icon asset |
| 62 | `latest.json` | Di chuyển sang `packaging/latest.json` | Metadata updater |
| 63 | `app_launch.log` | Xóa bỏ & đưa vào `.gitignore` | File log tạm |
| 64 | `workspace/cache/*` | Bỏ qua trong `.gitignore` | Không track file nhị phân mp3 tạm |

---

## 4. Kế Hoạch Sửa Reference Bị Vỡ (Bước 4)

1. **`tests/test_adversarial_challenger.py`**:
   - Dòng 498: Cập nhật đường dẫn test:
     ```python
     bat_path = Path("scripts/run_app.bat") if Path("scripts/run_app.bat").is_file() else Path("run_app.bat")
     ```
2. **`tests/test_manifest_and_packaging.py`**:
   - Dòng 382: Cập nhật đường dẫn test `reload_extension.bat`:
     ```python
     bat_path = PROJECT_ROOT / "scripts" / "reload_extension.bat"
     ```
3. **`scripts/export_all_ui_screenshots.py`**:
   - Dòng 35: Cập nhật `output_dir = repo_root / "docs" / "screenshots"`
4. **`AGENTS.md`**:
   - Dòng 45: Cập nhật lệnh chạy runbook:
     ```powershell
     .\scripts\run_app.bat
     # hoặc: .\.venv\Scripts\python.exe app.py
     ```
5. **Tạo wrapper tiện lợi tại root (Tùy chọn tương thích ngược)**:
   - Tạo file `run_app.bat` nhỏ tại root chỉ gồm 1 dòng: `call "%~dp0scripts\run_app.bat" %*` để người dùng quen nhấp đúp ở root vẫn chạy bình thường.
   - Tạo file `run_kappak.bat` nhỏ tại root: `call "%~dp0scripts\run_kappak.bat" %*`.

---

## 5. Kế Hoạch Thực Hiện Tiếp Theo (Sau Khi Được Duyệt)

- **Bước 2**: Cập nhật `.gitignore`, xóa `__pycache__` / cache khỏi git index (commit riêng).
- **Bước 3**: Di chuyển bằng `git mv` theo từng nhóm, mỗi nhóm commit riêng.
- **Bước 4**: Sửa các reference, chạy thử scripts và chạy pytest xác nhận 100% pass.
- **Bước 5**: Cập nhật `docs/handoff/PROGRESS.md` và gửi báo cáo tổng kết.
