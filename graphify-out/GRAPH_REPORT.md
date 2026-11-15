# Graph Report - openshorts  (2026-11-15)

## Corpus Check
- 193 files · ~211,243 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 26 file(s) not represented in the graph (top: (none) 10, .bat 4, .ttf 3)

## Summary
- 2881 nodes · 6176 edges · 133 communities (111 shown, 22 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 181 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `5dc9cd4a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- app.py
- saasshorts.py
- _seg
- _classify_failure
- test_panel_layout.py
- test_transcribe_backends.py
- hooks.py
- test_active_speaker.py
- asyncio
- os
- editor.py
- Request
- render-service/package.json
- split_layout.py
- openshorts_cli.py
- pages.js
- main.py
- auth.py
- billing.py
- test_layout_picker.py
- screencast_layout.py
- test_camera_inset.py
- OpenShorts
- metering.py
- s3_uploader.py
- render
- api_keys.py
- zoom_curve
- _request
- session
- lucide-react
- remotion/package.json
- models.py
- renderer
- api.js
- _TransientHTTPError
- Settings
- ref_react
- email_policy.py
- gemini_worker.py
- numpy
- test_reframe_endpoint.py
- config.py
- App.jsx
- test_gemini_retry.py
- with
- json
- dashboard/package.json
- openrouter_client.py
- _lock_onto
- _canonical_clip_file
- test_clip_selection.py
- main.jsx
- SaaShortsTab.jsx
- _entitles
- social_profiles.py
- remotion/compositions/HookOverlay.tsx
- test_mcp_endpoint.py
- db
- src/lib/types.ts
- test_subtitles.py
- subtitles.py
- assert_public_url
- _run
- _run
- ClipEditor.jsx
- subprocess
- test_process_handover.py
- analyze_scene
- test_short_source_gate.py
- resolve_post_profile
- clip_count_targets
- free_plan_eligible
- devDependencies
- remotion/compositions/Subtitles.tsx
- remotion/lib/types.ts
- mcp_server.py
- src/compositions/HookOverlay.tsx
- src/compositions/VideoEffects.tsx
- compilerOptions
- generate_ass
- handle_message
- storage.py
- src/compositions/Subtitles.tsx
- compilerOptions
- test_filename_limits.py
- emails.py
- run_cut_concat
- friendly_logs
- delivery_size
- scene_detection.py
- test_generation_controls.py
- remotion/compositions/ShortVideo.tsx
- snap_clip_to_words
- ollama_client.py
- get_viral_clips
- server.json
- clip_duration_bounds
- ScheduleWeekModal.jsx
- perform_recut
- alerts.py
- _escape_ffmpeg_filter_value
- generate_srt
- merge_continuation_words
- pytest
- TestAutoCaptionDefaults
- custom_client.py
- eslint.config.js
- vite.config.js
- proxy_watch_tick
- clip_picker_html
- resolve_upload_post
- TestBurnFilterFonts
- scripts
- openshorts
- normalize_segments
- download_youtube_video
- subtitle_minutes_for
- split_geometry
- EnvSettings.jsx
- TestJumpConfirmation
- attribute_windows
- hold
- test_job_error_text.py
- test_proxy_watch.py
- speaker_xs
- translate.py
- emphasis_times
- _watch_targets
- React + Vite
- session

## God Nodes (most connected - your core abstractions)
1. `session()` - 43 edges
2. `lucide-react` - 37 edges
3. `App()` - 32 edges
4. `Settings` - 29 edges
5. `video_encode_args()` - 29 edges
6. `render()` - 29 edges
7. `getApiUrl()` - 28 edges
8. `User` - 27 edges
9. `apiJson()` - 27 edges
10. `generate_ass()` - 26 edges

## Surprising Connections (you probably didn't know these)
- `_notify_clips_ready()` --uses--> `User`  [INFERRED]
  app.py → cloud/models.py
- `_notify_clip_activity()` --uses--> `User`  [INFERRED]
  app.py → cloud/models.py
- `_webhook_clip_entries()` --uses--> `UserVideo`  [INFERRED]
  app.py → cloud/models.py
- `restore_project()` --uses--> `Project`  [INFERRED]
  app.py → cloud/models.py
- `call_tool()` --indirect_call--> `client()`  [INFERRED]
  mcp_server.py → cloud/storage.py

## Import Cycles
- 2-file cycle: `render-service/src/render-worker.ts -> render-service/src/server.ts -> render-service/src/render-worker.ts`
- 2-file cycle: `cloud/__init__.py -> cloud/auth.py -> cloud/__init__.py`
- 2-file cycle: `cloud/__init__.py -> cloud/oauth.py -> cloud/__init__.py`
- 2-file cycle: `cloud/__init__.py -> cloud/digest.py -> cloud/__init__.py`
- 2-file cycle: `cloud/__init__.py -> cloud/api_keys.py -> cloud/__init__.py`
- 2-file cycle: `cloud/__init__.py -> cloud/billing.py -> cloud/__init__.py`
- 2-file cycle: `cloud/__init__.py -> cloud/metering.py -> cloud/__init__.py`
- 2-file cycle: `cloud/__init__.py -> cloud/social_profiles.py -> cloud/__init__.py`
- 2-file cycle: `cloud/__init__.py -> cloud/videos.py -> cloud/__init__.py`
- 2-file cycle: `cloud/database.py -> cloud/models.py -> cloud/database.py`
- 3-file cycle: `cloud/__init__.py -> cloud/billing.py -> cloud/auth.py -> cloud/__init__.py`
- 3-file cycle: `cloud/__init__.py -> cloud/oauth.py -> cloud/auth.py -> cloud/__init__.py`
- 3-file cycle: `cloud/__init__.py -> cloud/videos.py -> cloud/auth.py -> cloud/__init__.py`
- 3-file cycle: `cloud/__init__.py -> cloud/auth.py -> cloud/api_keys.py -> cloud/__init__.py`
- 3-file cycle: `cloud/__init__.py -> cloud/auth.py -> cloud/metering.py -> cloud/__init__.py`
- 3-file cycle: `cloud/__init__.py -> cloud/videos.py -> cloud/metering.py -> cloud/__init__.py`
- 4-file cycle: `cloud/__init__.py -> cloud/billing.py -> cloud/auth.py -> cloud/api_keys.py -> cloud/__init__.py`
- 4-file cycle: `cloud/__init__.py -> cloud/oauth.py -> cloud/auth.py -> cloud/api_keys.py -> cloud/__init__.py`
- 4-file cycle: `cloud/__init__.py -> cloud/videos.py -> cloud/auth.py -> cloud/api_keys.py -> cloud/__init__.py`
- 4-file cycle: `cloud/__init__.py -> cloud/billing.py -> cloud/auth.py -> cloud/metering.py -> cloud/__init__.py`

## Communities (133 total, 22 thin omitted)

### Community 0 - "app.py"
Cohesion: 0.05
Nodes (35): AITestBody, _archive_managed_job(), CaptionWordIn, EditRequest, EffectsGenerateRequest, EnvUpdateBody, get_config(), health() (+27 more)

### Community 1 - "saasshorts.py"
Cohesion: 0.05
Nodes (30): remove_subtitles(), RemoveSubtitlesRequest, run_analysis(), saasshorts_voices(), _strip_burned_captions(), _config(), _post(), track() (+22 more)

### Community 2 - "_seg"
Cohesion: 0.11
Nodes (11): run_recut(), rebase_segments(), snap_segments(), transcript_words(), virtual_transcript(), within_range(), _seg(), TestRangeMath (+3 more)

### Community 3 - "_classify_failure"
Cohesion: 0.22
Nodes (12): _classify_failure(), test_blocked_content_is_not_reported_as_outage(), test_ffmpeg(), test_gemini(), test_no_audio(), test_no_usable_clips_is_not_reported_as_outage(), test_proxy(), test_recovered_download_attempts_do_not_mask_the_terminal_error() (+4 more)

### Community 4 - "test_panel_layout.py"
Cohesion: 0.07
Nodes (18): analyze_scene(), detect_panel_scenes(), neighbour_gaps(), panel_filtergraph(), panel_geometry(), tile_grid(), usable_faces(), well_separated() (+10 more)

### Community 5 - "test_transcribe_backends.py"
Cohesion: 0.06
Nodes (35): fake_nemo(), fake_run(), _payload(), test_cli_resolution_is_memoized(), test_detect_language_defaults_to_en_for_short_text(), test_empty_words_fall_back_to_joined_text(), test_env_semaphore_invalid_value_falls_back_to_one(), test_env_semaphore_picks_up_live_change() (+27 more)

### Community 6 - "hooks.py"
Cohesion: 0.05
Nodes (22): run_hook(), add_hook_to_video(), _break_long_word(), create_hook_image(), download_font_if_needed(), _draw_mixed(), _emoji_scale(), _load_emoji_font() (+14 more)

### Community 7 - "test_active_speaker.py"
Cohesion: 0.19
Nodes (5): is_conversation(), mouth_region(), shares(), TestMouthRegion, TestShares

### Community 8 - "asyncio"
Cohesion: 0.08
Nodes (20): _archive_clip_edit_bg(), _run(), _clip_recipe_parts(), get_source_video(), lifespan(), _locate_source(), _probe_youtube_quality(), process_queue() (+12 more)

### Community 9 - "os"
Cohesion: 0.11
Nodes (14): cleanup_jobs(), _clear_resume_manifest(), _dir_size(), _enforce_output_size_cap(), _enforce_uploads_size_cap(), _enqueue_job(), enqueue_output(), _recover_jobs_from_disk() (+6 more)

### Community 10 - "editor.py"
Cohesion: 0.06
Nodes (11): run_edit(), run_effects_generation(), build_filter_string(), normalize_edits(), _zoom_term(), EditDecision, EditPlan, VideoEditor (+3 more)

### Community 11 - "Request"
Cohesion: 0.06
Nodes (41): add_hook(), add_subtitles(), _assert_job_owner(), edit_clip(), _ensure_job_files(), gemini_missing_error(), generate_effects_config(), get_clip_edl() (+33 more)

### Community 12 - "render-service/package.json"
Cohesion: 0.06
Nodes (42): express, @remotion/bundler, @remotion/renderer, tsx, @types/express, @types/uuid, uuid, dependencies (+34 more)

### Community 13 - "split_layout.py"
Cohesion: 0.14
Nodes (7): as_box(), _centre(), dedupe_faces(), _iou(), split_filtergraph(), _two_largest(), TestSplitFiltergraph

### Community 14 - "openshorts_cli.py"
Cohesion: 0.07
Nodes (21): get_env(), _absolutize(), _base(), cmd_clips(), cmd_process(), cmd_publish(), cmd_quota(), cmd_status() (+13 more)

### Community 15 - "pages.js"
Cohesion: 0.11
Nodes (37): CANONICAL_ANSWERS, CITED_STATS, COMPARISON_ROWS, COMPETITORS, EDITIONS, PIPELINE_STEPS, SAME_AS, SITE (+29 more)

### Community 16 - "main.py"
Cohesion: 0.07
Nodes (13): analyze_scenes_strategy(), create_general_frame(), detect_face_candidates(), detect_person_yolo(), detect_scenes(), _detection_frame(), _ensure_dir(), finalize_clip_passthrough() (+5 more)

### Community 17 - "auth.py"
Cohesion: 0.12
Nodes (16): AttributionPayload, _clip(), CurrentUser, _decode_jwt(), get_current_user_optional(), get_current_user_required(), get_me(), issue_jwt() (+8 more)

### Community 18 - "billing.py"
Cohesion: 0.10
Nodes (25): _apply_topup(), _blocking_sub_status(), CheckoutRequest, create_checkout(), create_portal(), end_trial(), ensure_stripe_customer(), get_catalog() (+17 more)

### Community 19 - "test_layout_picker.py"
Cohesion: 0.09
Nodes (12): apply(), _module_flags(), pick(), pick_and_apply(), sample_frames(), fake_modules(), TestApply, TestDecisionMapping (+4 more)

### Community 20 - "screencast_layout.py"
Cohesion: 0.08
Nodes (12): content_bands(), detect_faces_full_res(), detect_screencast_scenes(), _face_centre(), overlapping_width(), screencast_filtergraph(), speaker_crop(), TestContentBands (+4 more)

### Community 21 - "test_camera_inset.py"
Cohesion: 0.09
Nodes (11): detect(), inset_box(), inset_filtergraph(), is_cornered(), nearest_corner(), usable(), TestInsetBox, TestInsetFiltergraph (+3 more)

### Community 22 - "OpenShorts"
Cohesion: 0.08
Nodes (33): Completion webhooks, Hook text overlays, Async job queue (semaphore concurrency), Auto layout picker, MCP server (/mcp), NeMo-Speech.cpp, OpenShorts, React dashboard (Vite + Tailwind) (+25 more)

### Community 23 - "metering.py"
Cohesion: 0.09
Nodes (20): _load_current_user(), setup_async(), _active_subscription(), _balance(), _D(), free_period_end(), get_balance(), _now() (+12 more)

### Community 24 - "s3_uploader.py"
Cohesion: 0.08
Nodes (17): gallery_html_page(), run(), saasshorts_actor_gallery(), run_generation(), log_msg(), run(), saasshorts_video_gallery(), video_html_page() (+9 more)

### Community 25 - "render"
Cohesion: 0.09
Nodes (17): hwaccel_decode_args(), _analyze_trajectory(), apply_crop_overrides(), concat_list_content(), dedupe_sendcmd_lines(), full_width_content_height(), general_filtergraph(), render() (+9 more)

### Community 26 - "api_keys.py"
Cohesion: 0.12
Nodes (13): create_key(), CreateKeyRequest, generate_key(), hash_key(), list_keys(), looks_like_key(), _now(), revoke_key() (+5 more)

### Community 27 - "zoom_curve"
Cohesion: 0.11
Nodes (7): crop_boxes(), _ease(), sendcmd_lines(), zoom_curve(), TestCropBoxes, TestSendcmdLines, TestZoomCurve

### Community 28 - "_request"
Cohesion: 0.09
Nodes (8): fake_recut(), job(), _request(), TestGetEdl, TestMcpTool, TestRerenderPaths, TestRerenderPersistence, TestRerenderValidation

### Community 29 - "session"
Cohesion: 0.10
Nodes (20): _notify_clips_ready(), purge_stale_magic_tokens(), session(), is_free_user(), ClipExpiryWarning, MagicLinkToken, Project, UserVideo (+12 more)

### Community 30 - "lucide-react"
Cohesion: 0.12
Nodes (30): ENTRANCE_OPTIONS, HOOK_STYLES, HookModal(), loadHookPrefs(), POSITION_OPTIONS, SIZE_OPTIONS, fmt(), PLAN_ORDER (+22 more)

### Community 31 - "remotion/package.json"
Cohesion: 0.08
Nodes (34): @remotion/cli, @remotion/google-fonts, @remotion/layout-utils, dependencies, react@^18.2.0, react-dom@^18.2.0, remotion@^4.0.0, @remotion/cli@^4.0.0 (+26 more)

### Community 32 - "models.py"
Cohesion: 0.09
Nodes (14): _do_run(), run_migrations_online(), _notify_clip_activity(), send_telegram(), get_db(), get_sessionmaker(), init_engine(), _digest_loop() (+6 more)

### Community 33 - "renderer"
Cohesion: 0.07
Nodes (31): GPU, build, container_name, deploy, ports, restart, volumes, args (+23 more)

### Community 34 - "api.js"
Cohesion: 0.13
Nodes (26): AccountPage(), fmt1(), PAYMENT_ISSUE_STATES, ApiKeysCard(), HistoryTab(), fmt(), PLAN_BLURB, PLAN_ORDER (+18 more)

### Community 35 - "_TransientHTTPError"
Cohesion: 0.11
Nodes (16): run_translate(), no_sleep(), test_gives_up_after_max_attempts(), always_fails(), test_non_transient_fails_fast(), test_succeeds_after_transient_failures(), flaky(), create_dubbing_project() (+8 more)

### Community 37 - "ref_react"
Cohesion: 0.17
Nodes (15): Gallery(), GalleryCard(), FALLBACK_FREE_MODELS, KeyInput(), MediaInput(), SUPPORTED_PLATFORMS, ProcessingAnimation(), fmt() (+7 more)

### Community 38 - "email_policy.py"
Cohesion: 0.06
Nodes (13): classify_mx_hosts(), disposable_count(), _get_resolver(), _implicit_mx(), is_disposable(), mx_verdict(), normalize_email(), _resolve() (+5 more)

### Community 39 - "gemini_worker.py"
Cohesion: 0.11
Nodes (23): _calculate_cost_analysis(), _config_for_strategy(), _configure_stdio(), DetailClipModel, DetailResponse, _escape_invalid_unicode_escapes(), _extract_json_candidate(), GeminiBlockedError (+15 more)

### Community 40 - "numpy"
Cohesion: 0.18
Nodes (6): audio_envelope(), decode_activity(), normalise_activity(), verdicts_for_scene(), detect_split_scenes(), TestNormaliseActivity

### Community 41 - "test_reframe_endpoint.py"
Cohesion: 0.10
Nodes (7): fake_recut(), job(), _request(), TestApplyCropOverrides, TestReframeRender, TestReframeValidation, TestRerenderClearsSceneOverrides

### Community 42 - "config.py"
Cohesion: 0.10
Nodes (8): _flag(), is_enabled(), validate_required(), setup_sync(), google_callback(), google_login(), _now(), register()

### Community 43 - "App.jsx"
Cohesion: 0.18
Nodes (18): App(), decrypt(), encrypt(), formatRetention(), HistoryTab, isAutoProfileId(), pollJob(), ProfileNetworkIcons() (+10 more)

### Community 44 - "test_gemini_retry.py"
Cohesion: 0.12
Nodes (14): _BlockedResponse, _PF, _Reason, _client(), _FakeModels, _FakeResponse, _no_sleep(), test_gives_up_after_three_attempts() (+6 more)

### Community 45 - "with"
Cohesion: 0.10
Nodes (23): runs-on, steps, run, defaults, runs-on, steps, jobs, backend-tests (+15 more)

### Community 46 - "json"
Cohesion: 0.08
Nodes (18): _check_analytics_rate(), _check_probe_rate(), download_all_clips(), layout_env(), _maybe_send_quota_email(), _media_duration_seconds(), process_endpoint(), _reject_short_source() (+10 more)

### Community 47 - "dashboard/package.json"
Cohesion: 0.12
Nodes (22): dependencies, lucide-react@^0.344.0, react@^18.2.0, react-dom@^18.2.0, remotion@^4.0.447, @remotion/media@^4.0.447, @remotion/media-utils@^4.0.447, @remotion/player@^4.0.447 (+14 more)

### Community 48 - "openrouter_client.py"
Cohesion: 0.13
Nodes (11): call_openrouter(), get_effective_ai_provider(), _get_openai_client(), is_openrouter_key(), resolve_openrouter_key(), resolve_openrouter_model(), run_openrouter_detail(), run_openrouter_score() (+3 more)

### Community 49 - "_lock_onto"
Cohesion: 0.33
Nodes (4): _face(), _lock_onto(), TestSwitchCooldown, _tracker()

### Community 50 - "_canonical_clip_file"
Cohesion: 0.16
Nodes (6): _canonical_clip_file(), _strip_burned_hook(), TestCanonicalClipFile, TestLayerChain, TestStripBurnedHook, _touch()

### Community 51 - "test_clip_selection.py"
Cohesion: 0.15
Nodes (7): build_transcript_windows(), compact_words(), lookup_model_prices(), _seg(), TestBuildTranscriptWindows, TestCompactWords, TestPricing

### Community 52 - "main.jsx"
Cohesion: 0.14
Nodes (17): LoginModal(), DemoFigure(), FAQItem(), FAQS, HOSTED_VS_SELF, PricingPage(), TRUST_CARDS, DOCS (+9 more)

### Community 53 - "SaaShortsTab.jsx"
Cohesion: 0.27
Nodes (9): loadCache(), SaaShortsTab(), saveCache(), STEPS, STYLE_OPTIONS, DragDropZone(), STEPS, ThumbnailStudio() (+1 more)

### Community 54 - "_entitles"
Cohesion: 0.14
Nodes (5): _entitles(), _sub(), TestAttentionStates, TestCheckoutBlockingStates, TestEntitles

### Community 55 - "social_profiles.py"
Cohesion: 0.20
Nodes (7): UploadPostProfile, _auth_headers(), _create_remote_profile(), ensure_profile(), get_connect_url(), profile_username_for(), social_connect()

### Community 56 - "remotion/compositions/HookOverlay.tsx"
Cohesion: 0.20
Nodes (12): HOOK_LOOKS, HookBox(), HookBoxProps, HookLook, HookOverlay(), HookOverlayProps, POSITION_STYLE, SIZE_SCALE (+4 more)

### Community 57 - "test_mcp_endpoint.py"
Cohesion: 0.11
Nodes (7): _call(), _post(), TestCloudModeAuth, TestSelfHostQuota, TestToolsThroughRealEndpoints, TestTransport, TestWebhookSigning

### Community 58 - "db"
Cohesion: 0.10
Nodes (19): depends_on, environment, condition, container_name, environment, healthcheck, image, restart (+11 more)

### Community 59 - "src/lib/types.ts"
Cohesion: 0.11
Nodes (17): captionWordSchema, effectsConfigSchema, effectSegmentSchema, hookConfigSchema, HookEntrance, HookPosition, HookSize, HookStyle (+9 more)

### Community 60 - "test_subtitles.py"
Cohesion: 0.16
Nodes (6): run_burn(), burn_subtitles(), _clamp_number(), hex_to_ass_color(), _sanitize_font_name(), TestStyleSanitizing

### Community 61 - "subtitles.py"
Cohesion: 0.13
Nodes (11): run_transcribe_srt(), _ass_time(), _collect_word_blocks(), _configure_stdio(), _dim_hex_color(), _escape_ass_text(), generate_srt_from_video(), _hex_to_ass_inline_color() (+3 more)

### Community 62 - "assert_public_url"
Cohesion: 0.19
Nodes (6): _deliver_webhook(), _sign_webhook(), probe_url_minutes(), assert_public_url(), _ip_is_public(), UnsafeURLError

### Community 63 - "_run"
Cohesion: 0.17
Nodes (5): _err_tool(), _run(), TestInitialize, TestNotificationsAndErrors, TestTools

### Community 64 - "_run"
Cohesion: 0.21
Nodes (5): _req(), _run(), TestResourceSurface, TestToolWiring, fake()

### Community 65 - "ClipEditor.jsx"
Cohesion: 0.36
Nodes (7): ClipEditor(), editorReducer(), fmt(), SEGMENT_COLORS, totalOf(), TranscriptChunk, QuotaError

### Community 66 - "subprocess"
Cohesion: 0.09
Nodes (20): probe_file_minutes(), audio_encode_args(), hwaccel_available(), nvenc_available(), _probe_hwaccel(), _probe_nvenc(), reset_encoder_cache(), video_encode_args() (+12 more)

### Community 67 - "test_process_handover.py"
Cohesion: 0.26
Nodes (9): _post_process(), _submitted_job(), test_empty_transcript_is_not_forwarded(), test_handover_links_source_and_transcript(), test_handover_still_requires_attestation(), test_handover_without_ready_transcript_still_processes(), test_session_with_missing_video_404s(), test_unknown_session_404s() (+1 more)

### Community 68 - "analyze_scene"
Cohesion: 0.29
Nodes (4): analyze_scene(), face(), TestAnalyzeScene, two_shot()

### Community 69 - "test_short_source_gate.py"
Cohesion: 0.23
Nodes (10): dirs(), _post_process(), _stub_probe(), test_gate_disabled_lets_short_sources_through(), test_long_url_source_passes(), test_short_thumbnail_session_is_rejected(), test_short_upload_is_rejected_and_cleaned_up(), test_short_url_rejected_even_with_force_low_quality() (+2 more)

### Community 70 - "resolve_post_profile"
Cohesion: 0.13
Nodes (4): resolve_post_profile(), TestResolvePostProfileInCloud, TestResolvePostProfileSelfHosted, TestScheduledPostsAreFilteredByProfile

### Community 71 - "clip_count_targets"
Cohesion: 0.20
Nodes (3): clip_count_targets(), TestClipCountTargets, TestDetailPromptCarriesTheCount

### Community 72 - "free_plan_eligible"
Cohesion: 0.42
Nodes (3): free_plan_eligible(), TestFreePlanEligible, _user()

### Community 73 - "devDependencies"
Cohesion: 0.13
Nodes (15): devDependencies, autoprefixer@^10.4.23, eslint@^8.57.0, eslint-plugin-react@^7.34.0, postcss@^8.5.6, tailwindcss@^3.4.19, @types/react@^18.2.64, @types/react-dom@^18.2.21 (+7 more)

### Community 74 - "remotion/compositions/Subtitles.tsx"
Cohesion: 0.25
Nodes (13): POSITION_MAP, SubtitleBlock(), SubtitleBlockProps, Subtitles(), SubtitlesProps, WordSpan(), WordSpanProps, CaptionBlock (+5 more)

### Community 75 - "remotion/lib/types.ts"
Cohesion: 0.13
Nodes (14): captionWordSchema, effectsConfigSchema, effectSegmentSchema, hookConfigSchema, HookEntrance, HookPosition, HookSize, HookStyle (+6 more)

### Community 76 - "mcp_server.py"
Cohesion: 0.21
Nodes (10): _api_error(), _clip_summaries(), mcp_get(), _tool_add_subtitles(), _tool_get_job_status(), _tool_get_quota(), _tool_list_clips(), _tool_process_video() (+2 more)

### Community 77 - "src/compositions/HookOverlay.tsx"
Cohesion: 0.20
Nodes (12): HOOK_LOOKS, HookBox(), HookBoxProps, HookLook, HookOverlayProps, POSITION_STYLE, SIZE_SCALE, textStroke() (+4 more)

### Community 78 - "src/compositions/VideoEffects.tsx"
Cohesion: 0.23
Nodes (13): HookOverlay(), ShortVideo(), Subtitles(), getInterpolatedValues(), InterpolatedValues, lerp(), lerpFromDefaults(), lerpSegments() (+5 more)

### Community 79 - "compilerOptions"
Cohesion: 0.13
Nodes (14): compilerOptions, declaration, esModuleInterop, forceConsistentCasingInFileNames, module, moduleResolution, outDir, resolveJsonModule (+6 more)

### Community 80 - "generate_ass"
Cohesion: 0.40
Nodes (3): generate_ass(), TestGenerateAss, _w()

### Community 81 - "handle_message"
Cohesion: 0.20
Nodes (9): _authorized(), _billing_enabled(), call_tool(), _client(), handle_message(), mcp_endpoint(), tool_caller(), _rpc_error() (+1 more)

### Community 82 - "storage.py"
Cohesion: 0.21
Nodes (8): client(), delete_key(), delete_prefix(), download_file(), list_keys(), presigned_get(), upload_file(), user_prefix()

### Community 83 - "src/compositions/Subtitles.tsx"
Cohesion: 0.25
Nodes (12): POSITION_MAP, SubtitleBlock(), SubtitleBlockProps, SubtitlesProps, WordSpan(), WordSpanProps, CaptionBlock, getActiveWordIndex() (+4 more)

### Community 84 - "compilerOptions"
Cohesion: 0.14
Nodes (13): compilerOptions, declaration, esModuleInterop, forceConsistentCasingInFileNames, jsx, module, moduleResolution, outDir (+5 more)

### Community 85 - "test_filename_limits.py"
Cohesion: 0.14
Nodes (3): TestHookTempName, TestSanitizeFilename, TestTruncateBytes

### Community 86 - "emails.py"
Cohesion: 0.20
Nodes (6): send_clips_expiring_email(), send_clips_ready_email(), send_email(), send_magic_link_email(), send_out_of_minutes_email(), _send_sync()

### Community 87 - "run_cut_concat"
Cohesion: 0.17
Nodes (6): _clip_scene_workfile(), build(), concat_command(), cut_commands(), run_cut_concat(), TestFfmpegCommands

### Community 88 - "friendly_logs"
Cohesion: 0.27
Nodes (8): friendly_log_line(), friendly_logs(), _strip_paths(), test_consecutive_duplicates_collapse(), test_errors_kept_without_paths(), test_no_paths_ever_leak(), test_real_job_produces_clean_user_view(), test_technical_lines_are_hidden()

### Community 90 - "scene_detection.py"
Cohesion: 0.20
Nodes (6): _detect_pyscenedetect(), detect_scenes(), _detect_transnetv2(), _extract_frames_small(), _get_tn2_model(), _merge_short_scenes()

### Community 91 - "test_generation_controls.py"
Cohesion: 0.25
Nodes (3): _clean_env(), _templates(), TestPromptTemplates

### Community 92 - "remotion/compositions/ShortVideo.tsx"
Cohesion: 0.19
Nodes (13): renderInBrowser(), ShortVideo(), getInterpolatedValues(), InterpolatedValues, lerp(), lerpFromDefaults(), lerpSegments(), lerpToDefaults() (+5 more)

### Community 93 - "snap_clip_to_words"
Cohesion: 0.38
Nodes (3): snap_clip_to_words(), TestSnapClipToWords, _word()

### Community 94 - "ollama_client.py"
Cohesion: 0.47
Nodes (3): call_ollama(), ollama_model(), ollama_url()

### Community 95 - "get_viral_clips"
Cohesion: 0.27
Nodes (6): _ai_provider(), get_viral_clips(), _openrouter_key(), _openrouter_model(), _run_ai_stage(), _use_openrouter()

### Community 96 - "server.json"
Cohesion: 0.20
Nodes (9): description, name, remotes, repository, source, url, $schema, version (+1 more)

### Community 97 - "clip_duration_bounds"
Cohesion: 0.23
Nodes (3): clip_duration_bounds(), get_visual_clips(), TestClipDurationBounds

### Community 98 - "ScheduleWeekModal.jsx"
Cohesion: 0.31
Nodes (8): DAYS, detectTimezone(), formatDate(), getDayLabel(), MONTHS, PLATFORM_OPTIONS, ScheduleWeekModal(), TIMEZONES

### Community 99 - "perform_recut"
Cohesion: 0.16
Nodes (3): _main_attr(), perform_recut(), TestPerformRecut

### Community 100 - "alerts.py"
Cohesion: 0.21
Nodes (6): _cooldown_ok(), _looks_like_proxy_error(), _probe_one(), record_job_outcome(), send_admin_alert(), _watch_update()

### Community 102 - "generate_srt"
Cohesion: 0.36
Nodes (3): format_srt_block(), generate_srt(), TestGenerateSrt

### Community 106 - "custom_client.py"
Cohesion: 0.43
Nodes (4): ai_api_key(), ai_base_url(), ai_model(), call_custom()

### Community 107 - "eslint.config.js"
Cohesion: 0.29
Nodes (4): eslint-plugin-react-hooks@^4.6.0, eslint-plugin-react-refresh@^0.4.5, eslint-plugin-react-hooks, eslint-plugin-react-refresh

### Community 108 - "vite.config.js"
Cohesion: 0.29
Nodes (6): vite@^4.5.3, @vitejs/plugin-react@^4.2.1, backend, renderer, vite, @vitejs/plugin-react

### Community 109 - "proxy_watch_tick"
Cohesion: 0.37
Nodes (4): proxy_watch_tick(), _probes(), _run(), TestWatchTick

### Community 111 - "resolve_upload_post"
Cohesion: 0.12
Nodes (8): get_social_user(), post_to_socials(), resolve_upload_post(), _safe_under(), SocialPostRequest, thumbnail_publish(), has_active_entitlement(), upload_post_key()

### Community 113 - "scripts"
Cohesion: 0.40
Nodes (5): scripts, build, dev, lint, preview

### Community 117 - "normalize_segments"
Cohesion: 0.23
Nodes (3): normalize_segments(), RecutError, TestNormalizeSegments

### Community 118 - "download_youtube_video"
Cohesion: 0.20
Nodes (7): download_youtube_video(), _attempt(), _base_opts(), _progress_hook(), plan_download_attempts(), sanitize_filename(), truncate_bytes()

### Community 121 - "EnvSettings.jsx"
Cohesion: 0.31
Nodes (8): ALL_FIELDS, ColabGuide(), EnvField(), EnvSettings(), GROUPS, isSecretKey(), PROVIDER_CARDS, PROVIDER_CHOICES

### Community 125 - "test_job_error_text.py"
Cohesion: 0.36
Nodes (4): _classify(), test_download_failure_survives_trailing_noise(), test_gemini_blip_is_not_blamed_on_ffmpeg(), test_silent_upload_reports_no_audio()

### Community 131 - "React + Vite"
Cohesion: 0.50
Nodes (3): Expanding the ESLint configuration, React Compiler, React + Vite

## Knowledge Gaps
- **5 isolated node(s):** `openshorts`, `fal.ai`, `Subject tracking stack (MediaPipe + YOLOv8)`, `Parakeet TDT 0.6B v3`, `Build-time SEO surface (vite-plugin-seo.js)`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 908 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **22 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `generate_ass()` connect `generate_ass` to `app.py`, `TestAutoCaptionDefaults`, `Request`, `test_subtitles.py`, `subtitles.py`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **What connects `openshorts`, `fal.ai`, `Subject tracking stack (MediaPipe + YOLOv8)` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `app.py` be split into smaller, more focused modules?**
  _Cohesion score 0.04858757062146893 - nodes in this community are weakly interconnected._
- **Why does `get_current_user_required()` connect `auth.py` to `app.py`, `os`, `billing.py`, `social_profiles.py`, `api_keys.py`, `session`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **Should `saasshorts.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05288207297726071 - nodes in this community are weakly interconnected._
- **Should `_seg` be split into smaller, more focused modules?**
  _Cohesion score 0.1053763440860215 - nodes in this community are weakly interconnected._
- **Should `test_panel_layout.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06885245901639345 - nodes in this community are weakly interconnected._