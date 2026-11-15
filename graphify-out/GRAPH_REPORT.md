# Graph Report - openshorts  (2026-11-16)

## Corpus Check
- 214 files · ~216,376 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 29 file(s) not represented in the graph (top: (none) 10, .ipynb 4, .bat 4)

## Summary
- 3018 nodes · 6533 edges · 157 communities (120 shown, 37 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 168 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f7108d19`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- asyncio
- saasshorts.py
- test_recut.py
- _classify_failure
- test_panel_layout.py
- test_transcribe_backends.py
- hooks.py
- test_active_speaker.py
- clips.py
- os
- _edit
- render-service/package.json
- analyze_scene
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
- routes/saasshorts.py
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
- _request
- config.py
- App.jsx
- test_gemini_retry.py
- with
- thumbnails.py
- dashboard/package.json
- process.py
- _lock_onto
- _canonical_clip_file
- test_clip_selection.py
- main.jsx
- social.py
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
- system.py
- video_encode_args
- test_process_handover.py
- pytest
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
- openrouter.py
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
- env_manager.py
- eslint.config.js
- vite.config.js
- proxy_watch_tick
- clip_picker_html
- typing
- TestBurnFilterFonts
- scripts
- openshorts
- normalize_segments
- run_pipeline
- subtitle_minutes_for
- transcribe_backends.py
- EnvSettings.jsx
- lucide-react
- attribute_windows
- hold
- test_job_error_text.py
- test_proxy_watch.py
- speaker_xs
- src/compositions/ShortVideo.tsx
- emphasis_times
- _watch_targets
- React + Vite
- TestApplyCropOverrides
- ffmpeg_utils.py
- TestRangeMath
- punch_in.py
- general_filtergraph
- argparse
- transcribe_media
- _EnvSemaphore
- crop_boxes
- mouth_region
- virtual_transcript
- fake_recut
- add_hook_to_video
- PlanChoiceModal.jsx
- RecutError

## God Nodes (most connected - your core abstractions)
1. `session()` - 44 edges
2. `lucide-react` - 36 edges
3. `App()` - 31 edges
4. `_assert_job_owner()` - 31 edges
5. `video_encode_args()` - 30 edges
6. `render()` - 30 edges
7. `Settings` - 29 edges
8. `getApiUrl()` - 29 edges
9. `apiJson()` - 27 edges
10. `generate_ass()` - 26 edges

## Surprising Connections (you probably didn't know these)
- `run_analysis()` --indirect_call--> `gemini_key()`  [INFERRED]
  server/routes/saasshorts.py → cloud/managed_keys.py
- `_deliver_webhook()` --indirect_call--> `assert_public_url()`  [INFERRED]
  server/jobs.py → security_utils.py
- `process_endpoint()` --indirect_call--> `assert_public_url()`  [INFERRED]
  server/routes/process.py → security_utils.py
- `saasshorts_actor_options()` --indirect_call--> `generate_actor_images()`  [INFERRED]
  server/routes/saasshorts.py → saasshorts.py
- `test_max_file_size_mb_reads_env_live()` --calls--> `_max_file_size_mb()`  [EXTRACTED]
  tests/test_env_knobs.py → server/state.py

## Import Cycles
- 2-file cycle: `render-service/src/render-worker.ts -> render-service/src/server.ts -> render-service/src/render-worker.ts`
- 2-file cycle: `cloud/__init__.py -> cloud/auth.py -> cloud/__init__.py`
- 2-file cycle: `cloud/__init__.py -> cloud/oauth.py -> cloud/__init__.py`
- 2-file cycle: `cloud/__init__.py -> cloud/digest.py -> cloud/__init__.py`
- 2-file cycle: `cloud/__init__.py -> cloud/social_profiles.py -> cloud/__init__.py`
- 2-file cycle: `cloud/__init__.py -> cloud/billing.py -> cloud/__init__.py`
- 2-file cycle: `cloud/__init__.py -> cloud/metering.py -> cloud/__init__.py`
- 2-file cycle: `cloud/__init__.py -> cloud/api_keys.py -> cloud/__init__.py`
- 2-file cycle: `cloud/__init__.py -> cloud/videos.py -> cloud/__init__.py`
- 2-file cycle: `cloud/database.py -> cloud/models.py -> cloud/database.py`
- 3-file cycle: `cloud/__init__.py -> cloud/auth.py -> cloud/api_keys.py -> cloud/__init__.py`
- 3-file cycle: `cloud/__init__.py -> cloud/billing.py -> cloud/auth.py -> cloud/__init__.py`
- 3-file cycle: `cloud/__init__.py -> cloud/videos.py -> cloud/auth.py -> cloud/__init__.py`
- 3-file cycle: `cloud/__init__.py -> cloud/oauth.py -> cloud/auth.py -> cloud/__init__.py`
- 3-file cycle: `cloud/__init__.py -> cloud/auth.py -> cloud/metering.py -> cloud/__init__.py`
- 3-file cycle: `cloud/__init__.py -> cloud/videos.py -> cloud/metering.py -> cloud/__init__.py`
- 4-file cycle: `cloud/__init__.py -> cloud/billing.py -> cloud/auth.py -> cloud/api_keys.py -> cloud/__init__.py`
- 4-file cycle: `cloud/__init__.py -> cloud/videos.py -> cloud/auth.py -> cloud/api_keys.py -> cloud/__init__.py`
- 4-file cycle: `cloud/__init__.py -> cloud/oauth.py -> cloud/auth.py -> cloud/api_keys.py -> cloud/__init__.py`
- 4-file cycle: `cloud/__init__.py -> cloud/billing.py -> cloud/auth.py -> cloud/metering.py -> cloud/__init__.py`

## Communities (157 total, 37 thin omitted)

### Community 0 - "asyncio"
Cohesion: 0.09
Nodes (11): lifespan(), _deliver_webhook(), _job_error_text(), _notify_job_webhook(), process_queue(), _sign_webhook(), _webhook_clip_entries(), _max_concurrent_jobs() (+3 more)

### Community 1 - "saasshorts.py"
Cohesion: 0.08
Nodes (18): _config(), _post(), track(), composite_video(), _fal_run(), _fal_upload_file(), generate_actor_image(), generate_actor_images() (+10 more)

### Community 2 - "test_recut.py"
Cohesion: 0.21
Nodes (4): snap_segments(), transcript_words(), TestSnapSegments, TestTranscriptWords

### Community 3 - "_classify_failure"
Cohesion: 0.22
Nodes (12): _classify_failure(), test_blocked_content_is_not_reported_as_outage(), test_ffmpeg(), test_gemini(), test_no_audio(), test_no_usable_clips_is_not_reported_as_outage(), test_proxy(), test_recovered_download_attempts_do_not_mask_the_terminal_error() (+4 more)

### Community 4 - "test_panel_layout.py"
Cohesion: 0.07
Nodes (18): analyze_scene(), detect_panel_scenes(), neighbour_gaps(), panel_filtergraph(), panel_geometry(), tile_grid(), usable_faces(), well_separated() (+10 more)

### Community 5 - "test_transcribe_backends.py"
Cohesion: 0.10
Nodes (24): fake_nemo(), fake_run(), _payload(), test_detect_language_defaults_to_en_for_short_text(), test_empty_words_fall_back_to_joined_text(), test_nemo_cmd_uses_model_alias_and_json(), test_nemo_nonzero_exit_raises_with_stderr_tail(), test_nemo_transcript_matches_contract() (+16 more)

### Community 6 - "hooks.py"
Cohesion: 0.06
Nodes (19): _break_long_word(), create_hook_image(), download_font_if_needed(), _draw_mixed(), _emoji_scale(), _load_emoji_font(), _measure_width(), _render_emoji_chunk() (+11 more)

### Community 7 - "test_active_speaker.py"
Cohesion: 0.20
Nodes (5): is_conversation(), normalise_activity(), shares(), TestNormaliseActivity, TestShares

### Community 8 - "clips.py"
Cohesion: 0.07
Nodes (41): clip_recipe_parts(), clip_window(), load_metadata(), metadata_base_name(), save_metadata(), total_duration(), require_managed_entitlement(), reserve_managed_action() (+33 more)

### Community 9 - "os"
Cohesion: 0.04
Nodes (37): canonical_clip_file(), find_metadata_files(), latest_metadata(), strip_burned_captions(), strip_burned_hook(), upload_job_artifacts(), analyze_saas(), _format_ass_time() (+29 more)

### Community 10 - "_edit"
Cohesion: 0.16
Nodes (6): build_filter_string(), normalize_edits(), _zoom_term(), _edit(), TestBuildFilterString, TestNormalizeEdits

### Community 12 - "render-service/package.json"
Cohesion: 0.06
Nodes (42): express, @remotion/bundler, @remotion/renderer, tsx, @types/express, @types/uuid, uuid, dependencies (+34 more)

### Community 13 - "analyze_scene"
Cohesion: 0.08
Nodes (14): analyze_scene(), as_box(), _centre(), dedupe_faces(), detect_split_scenes(), _iou(), split_filtergraph(), split_geometry() (+6 more)

### Community 14 - "openshorts_cli.py"
Cohesion: 0.29
Nodes (12): _absolutize(), _base(), cmd_clips(), cmd_process(), cmd_publish(), cmd_quota(), cmd_status(), _die() (+4 more)

### Community 15 - "pages.js"
Cohesion: 0.11
Nodes (37): CANONICAL_ANSWERS, CITED_STATS, COMPARISON_ROWS, COMPETITORS, EDITIONS, PIPELINE_STEPS, SAME_AS, SITE (+29 more)

### Community 16 - "main.py"
Cohesion: 0.08
Nodes (14): get_video_resolution(), analyze_scenes_strategy(), detect_scenes(), finalize_clip_passthrough(), get_video_resolution(), process_video_to_vertical(), render_clip(), analyze_scenes_strategy() (+6 more)

### Community 17 - "auth.py"
Cohesion: 0.12
Nodes (17): AttributionPayload, _clip(), CurrentUser, _decode_jwt(), get_current_user_optional(), get_current_user_required(), get_me(), issue_jwt() (+9 more)

### Community 18 - "billing.py"
Cohesion: 0.10
Nodes (25): _apply_topup(), _blocking_sub_status(), CheckoutRequest, create_checkout(), create_portal(), end_trial(), ensure_stripe_customer(), get_catalog() (+17 more)

### Community 19 - "test_layout_picker.py"
Cohesion: 0.09
Nodes (12): apply(), _module_flags(), pick(), pick_and_apply(), sample_frames(), fake_modules(), TestApply, TestDecisionMapping (+4 more)

### Community 20 - "screencast_layout.py"
Cohesion: 0.08
Nodes (13): content_bands(), detect_content_ranges(), detect_faces_full_res(), detect_screencast_scenes(), _face_centre(), overlapping_width(), screencast_filtergraph(), speaker_crop() (+5 more)

### Community 21 - "test_camera_inset.py"
Cohesion: 0.09
Nodes (11): detect(), inset_box(), inset_filtergraph(), is_cornered(), nearest_corner(), usable(), TestInsetBox, TestInsetFiltergraph (+3 more)

### Community 22 - "OpenShorts"
Cohesion: 0.08
Nodes (33): Completion webhooks, Hook text overlays, Async job queue (semaphore concurrency), Auto layout picker, MCP server (/mcp), NeMo-Speech.cpp, OpenShorts, React dashboard (Vite + Tailwind) (+25 more)

### Community 23 - "metering.py"
Cohesion: 0.09
Nodes (21): setup_async(), _active_subscription(), _balance(), commit_reservation(), _D(), free_period_end(), get_balance(), _now() (+13 more)

### Community 24 - "routes/saasshorts.py"
Cohesion: 0.06
Nodes (23): generate_presigned_url(), get_s3_client(), list_actor_gallery(), list_all_clips(), list_video_gallery(), upload_actor_to_s3(), upload_file_to_s3(), upload_video_to_gallery() (+15 more)

### Community 25 - "render"
Cohesion: 0.11
Nodes (16): probe_file_minutes(), hwaccel_decode_args(), _run_ffmpeg(), _analyze_trajectory(), apply_crop_overrides(), concat_list_content(), dedupe_sendcmd_lines(), full_width_content_height() (+8 more)

### Community 26 - "api_keys.py"
Cohesion: 0.11
Nodes (14): create_key(), CreateKeyRequest, generate_key(), hash_key(), list_keys(), looks_like_key(), _now(), revoke_key() (+6 more)

### Community 27 - "zoom_curve"
Cohesion: 0.26
Nodes (3): _ease(), zoom_curve(), TestZoomCurve

### Community 28 - "_request"
Cohesion: 0.13
Nodes (5): _request(), TestGetEdl, TestRerenderPaths, TestRerenderPersistence, TestRerenderValidation

### Community 29 - "session"
Cohesion: 0.10
Nodes (19): purge_stale_magic_tokens(), session(), send_clips_expiring_email(), is_free_user(), ClipExpiryWarning, Project, UserVideo, job_key() (+11 more)

### Community 30 - "lucide-react"
Cohesion: 0.10
Nodes (28): ENTRANCE_OPTIONS, HOOK_STYLES, HookModal(), loadHookPrefs(), POSITION_OPTIONS, SIZE_OPTIONS, RemotionPreview(), clipDurationSeconds() (+20 more)

### Community 31 - "remotion/package.json"
Cohesion: 0.08
Nodes (34): @remotion/cli, @remotion/google-fonts, @remotion/layout-utils, dependencies, react@^18.2.0, react-dom@^18.2.0, remotion@^4.0.0, @remotion/cli@^4.0.0 (+26 more)

### Community 32 - "models.py"
Cohesion: 0.10
Nodes (12): _do_run(), run_migrations_online(), get_db(), get_sessionmaker(), init_engine(), _digest_loop(), _format(), send_daily_digest() (+4 more)

### Community 33 - "renderer"
Cohesion: 0.07
Nodes (31): GPU, build, container_name, deploy, ports, restart, volumes, args (+23 more)

### Community 34 - "api.js"
Cohesion: 0.15
Nodes (23): ClipEditor(), editorReducer(), fmt(), SEGMENT_COLORS, totalOf(), TranscriptChunk, fmt(), PLAN_BLURB (+15 more)

### Community 35 - "_TransientHTTPError"
Cohesion: 0.09
Nodes (18): get_languages(), run_translate(), no_sleep(), test_gives_up_after_max_attempts(), always_fails(), test_non_transient_fails_fast(), test_succeeds_after_transient_failures(), flaky() (+10 more)

### Community 37 - "ref_react"
Cohesion: 0.12
Nodes (25): Gallery(), GalleryCard(), FALLBACK_FREE_MODELS, KeyInput(), MediaInput(), SUPPORTED_PLATFORMS, ProcessingAnimation(), fmt() (+17 more)

### Community 38 - "email_policy.py"
Cohesion: 0.11
Nodes (5): classify_mx_hosts(), mx_verdict(), TestClassifyMxHosts, TestMxVerdict, nx()

### Community 39 - "gemini_worker.py"
Cohesion: 0.09
Nodes (24): _run_gemini_stage(), _calculate_cost_analysis(), _config_for_strategy(), _configure_stdio(), DetailClipModel, DetailResponse, _escape_invalid_unicode_escapes(), _extract_json_candidate() (+16 more)

### Community 40 - "numpy"
Cohesion: 0.33
Nodes (3): audio_envelope(), decode_activity(), verdicts_for_scene()

### Community 41 - "_request"
Cohesion: 0.23
Nodes (4): _request(), TestReframeRender, TestReframeValidation, TestRerenderClearsSceneOverrides

### Community 42 - "config.py"
Cohesion: 0.12
Nodes (8): _flag(), is_enabled(), validate_required(), setup_sync(), google_callback(), google_login(), _now(), register()

### Community 43 - "App.jsx"
Cohesion: 0.17
Nodes (16): App(), APP_TABS, decrypt(), encrypt(), formatRetention(), HistoryTab, isAutoProfileId(), pollJob() (+8 more)

### Community 44 - "test_gemini_retry.py"
Cohesion: 0.06
Nodes (17): VideoEditor, run_edit(), run_effects_generation(), _BlockedResponse, _PF, _Reason, _client(), _FakeModels (+9 more)

### Community 45 - "with"
Cohesion: 0.10
Nodes (23): runs-on, steps, run, defaults, runs-on, steps, jobs, backend-tests (+15 more)

### Community 46 - "thumbnails.py"
Cohesion: 0.08
Nodes (22): _assert_job_owner(), gemini_missing_error(), _owner_id(), resolve_gemini(), _user_from_request(), saasshorts_generate(), thumbnail_analyze(), thumbnail_describe() (+14 more)

### Community 47 - "dashboard/package.json"
Cohesion: 0.12
Nodes (22): dependencies, lucide-react@^0.344.0, react@^18.2.0, react-dom@^18.2.0, remotion@^4.0.447, @remotion/media@^4.0.447, @remotion/media-utils@^4.0.447, @remotion/player@^4.0.447 (+14 more)

### Community 48 - "process.py"
Cohesion: 0.07
Nodes (17): send_out_of_minutes_email(), _check_probe_rate(), _maybe_send_quota_email(), reserve_process_minutes(), _resolve_ai_provider(), _resolve_openrouter_model(), download_all_clips(), get_source_video() (+9 more)

### Community 49 - "_lock_onto"
Cohesion: 0.18
Nodes (5): _face(), _lock_onto(), TestJumpConfirmation, TestSwitchCooldown, _tracker()

### Community 50 - "_canonical_clip_file"
Cohesion: 0.17
Nodes (4): TestCanonicalClipFile, TestLayerChain, TestStripBurnedHook, _touch()

### Community 51 - "test_clip_selection.py"
Cohesion: 0.15
Nodes (7): build_transcript_windows(), compact_words(), lookup_model_prices(), _seg(), TestBuildTranscriptWindows, TestCompactWords, TestPricing

### Community 52 - "main.jsx"
Cohesion: 0.13
Nodes (19): LoginModal(), DemoFigure(), FAQItem(), FAQS, HOSTED_VS_SELF, PricingPage(), TRUST_CARDS, ProfileMenu() (+11 more)

### Community 53 - "social.py"
Cohesion: 0.10
Nodes (19): resolve_upload_post(), _check_analytics_rate(), get_social_user(), _post_row_views(), post_to_socials(), _scheduled_posts_for(), _social_analytics_auth(), social_cancel_scheduled() (+11 more)

### Community 54 - "_entitles"
Cohesion: 0.13
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
Cohesion: 0.14
Nodes (13): captionWordSchema, effectsConfigSchema, effectSegmentSchema, hookConfigSchema, HookEntrance, HookPosition, HookSize, HookStyle (+5 more)

### Community 60 - "test_subtitles.py"
Cohesion: 0.16
Nodes (6): run_burn(), burn_subtitles(), _clamp_number(), hex_to_ass_color(), _sanitize_font_name(), TestStyleSanitizing

### Community 61 - "subtitles.py"
Cohesion: 0.13
Nodes (11): run_transcribe_srt(), _ass_time(), _collect_word_blocks(), _configure_stdio(), _dim_hex_color(), _escape_ass_text(), generate_srt_from_video(), _hex_to_ass_inline_color() (+3 more)

### Community 62 - "assert_public_url"
Cohesion: 0.22
Nodes (4): probe_url_minutes(), assert_public_url(), _ip_is_public(), UnsafeURLError

### Community 63 - "_run"
Cohesion: 0.17
Nodes (5): _err_tool(), _run(), TestInitialize, TestNotificationsAndErrors, TestTools

### Community 64 - "_run"
Cohesion: 0.21
Nodes (5): _req(), _run(), TestResourceSurface, TestToolWiring, fake()

### Community 65 - "system.py"
Cohesion: 0.09
Nodes (15): AITestBody, _asr_list_models(), _asr_run_job(), ASRActionBody, download_asr_model(), EnvUpdateBody, get_asr_job_status(), get_asr_models() (+7 more)

### Community 66 - "video_encode_args"
Cohesion: 0.19
Nodes (11): reset_encoder_cache(), video_encode_args(), _clean_encoder_state(), test_auto_probes_only_once(), test_default_args_pin_historical_x264_settings(), test_encode_args_stay_free_of_metadata_flags(), test_missing_ffmpeg_binary_means_x264(), test_nvenc_mode_falls_back_to_x264_when_probe_fails() (+3 more)

### Community 67 - "test_process_handover.py"
Cohesion: 0.19
Nodes (11): dirs(), _post_process(), session(), _submitted_job(), test_empty_transcript_is_not_forwarded(), test_handover_links_source_and_transcript(), test_handover_still_requires_attestation(), test_handover_without_ready_transcript_still_processes() (+3 more)

### Community 68 - "pytest"
Cohesion: 0.11
Nodes (8): disposable_count(), _get_resolver(), _implicit_mx(), is_disposable(), normalize_email(), _resolve(), TestDisposable, TestNormalize

### Community 69 - "test_short_source_gate.py"
Cohesion: 0.23
Nodes (10): dirs(), _post_process(), _stub_probe(), test_gate_disabled_lets_short_sources_through(), test_long_url_source_passes(), test_short_thumbnail_session_is_rejected(), test_short_upload_is_rejected_and_cleaned_up(), test_short_url_rejected_even_with_force_low_quality() (+2 more)

### Community 70 - "resolve_post_profile"
Cohesion: 0.18
Nodes (3): resolve_post_profile(), TestResolvePostProfileInCloud, TestResolvePostProfileSelfHosted

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
Cohesion: 0.12
Nodes (15): captionWordSchema, effectsConfigSchema, effectSegmentSchema, hookConfigSchema, HookEntrance, HookPosition, HookSize, HookStyle (+7 more)

### Community 76 - "mcp_server.py"
Cohesion: 0.26
Nodes (10): _api_error(), _clip_summaries(), mcp_get(), _tool_add_subtitles(), _tool_get_job_status(), _tool_get_quota(), _tool_list_clips(), _tool_process_video() (+2 more)

### Community 77 - "src/compositions/HookOverlay.tsx"
Cohesion: 0.20
Nodes (12): HOOK_LOOKS, HookBox(), HookBoxProps, HookLook, HookOverlayProps, POSITION_STYLE, SIZE_SCALE, textStroke() (+4 more)

### Community 78 - "src/compositions/VideoEffects.tsx"
Cohesion: 0.38
Nodes (9): getInterpolatedValues(), InterpolatedValues, lerp(), lerpFromDefaults(), lerpSegments(), lerpToDefaults(), VideoEffectsProps, EffectsConfig (+1 more)

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
Nodes (13): POSITION_MAP, SubtitleBlock(), SubtitleBlockProps, Subtitles(), SubtitlesProps, WordSpan(), WordSpanProps, CaptionBlock (+5 more)

### Community 84 - "compilerOptions"
Cohesion: 0.14
Nodes (13): compilerOptions, declaration, esModuleInterop, forceConsistentCasingInFileNames, jsx, module, moduleResolution, outDir (+5 more)

### Community 85 - "test_filename_limits.py"
Cohesion: 0.14
Nodes (3): TestHookTempName, TestSanitizeFilename, TestTruncateBytes

### Community 86 - "emails.py"
Cohesion: 0.27
Nodes (4): send_clips_ready_email(), send_email(), send_magic_link_email(), _send_sync()

### Community 87 - "run_cut_concat"
Cohesion: 0.17
Nodes (6): concat_command(), cut_commands(), run_cut_concat(), _clip_scene_workfile(), build(), TestFfmpegCommands

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
Cohesion: 0.35
Nodes (10): getInterpolatedValues(), InterpolatedValues, lerp(), lerpFromDefaults(), lerpSegments(), lerpToDefaults(), VideoEffects(), VideoEffectsProps (+2 more)

### Community 93 - "snap_clip_to_words"
Cohesion: 0.38
Nodes (3): snap_clip_to_words(), TestSnapClipToWords, _word()

### Community 94 - "openrouter.py"
Cohesion: 0.13
Nodes (11): call_openrouter(), get_effective_ai_provider(), _get_openai_client(), is_openrouter_key(), resolve_openrouter_key(), resolve_openrouter_model(), run_openrouter_detail(), run_openrouter_score() (+3 more)

### Community 95 - "get_viral_clips"
Cohesion: 0.11
Nodes (15): ai_api_key(), ai_base_url(), ai_model(), call_custom(), _ai_provider(), _openrouter_key(), _openrouter_model(), _run_ai_stage() (+7 more)

### Community 96 - "server.json"
Cohesion: 0.20
Nodes (9): description, name, remotes, repository, source, url, $schema, version (+1 more)

### Community 98 - "ScheduleWeekModal.jsx"
Cohesion: 0.31
Nodes (8): DAYS, detectTimezone(), formatDate(), getDayLabel(), MONTHS, PLATFORM_OPTIONS, ScheduleWeekModal(), TIMEZONES

### Community 99 - "perform_recut"
Cohesion: 0.15
Nodes (4): _main_attr(), perform_recut(), run(), TestPerformRecut

### Community 100 - "alerts.py"
Cohesion: 0.15
Nodes (8): _cooldown_ok(), _looks_like_proxy_error(), _probe_one(), proxy_watch_loop(), record_job_outcome(), send_admin_alert(), send_telegram(), _watch_update()

### Community 102 - "generate_srt"
Cohesion: 0.36
Nodes (3): format_srt_block(), generate_srt(), TestGenerateSrt

### Community 106 - "env_manager.py"
Cohesion: 0.10
Nodes (7): apply_updates(), env_file_exists(), _mask(), masked_snapshot(), read_env_snapshot(), validate_updates(), get_env()

### Community 107 - "eslint.config.js"
Cohesion: 0.29
Nodes (4): eslint-plugin-react-hooks@^4.6.0, eslint-plugin-react-refresh@^0.4.5, eslint-plugin-react-hooks, eslint-plugin-react-refresh

### Community 108 - "vite.config.js"
Cohesion: 0.29
Nodes (6): vite@^4.5.3, @vitejs/plugin-react@^4.2.1, backend, renderer, vite, @vitejs/plugin-react

### Community 109 - "proxy_watch_tick"
Cohesion: 0.37
Nodes (4): proxy_watch_tick(), _probes(), _run(), TestWatchTick

### Community 111 - "typing"
Cohesion: 0.12
Nodes (5): gemini_key(), has_active_entitlement(), Job, EditDecision, EditPlan

### Community 113 - "scripts"
Cohesion: 0.40
Nodes (5): scripts, build, dev, lint, preview

### Community 117 - "normalize_segments"
Cohesion: 0.36
Nodes (3): normalize_segments(), _seg(), TestNormalizeSegments

### Community 118 - "run_pipeline"
Cohesion: 0.10
Nodes (14): audio_encode_args(), apply_watermark(), auto_caption_clip(), download_youtube_video(), _attempt(), _base_opts(), _progress_hook(), plan_download_attempts() (+6 more)

### Community 120 - "transcribe_backends.py"
Cohesion: 0.15
Nodes (10): test_cli_resolution_is_memoized(), test_missing_cli_raises_with_install_hint(), ensure_model_cached(), _extract_wav(), _nemo_asr_url(), reset_runtime_cache(), _resolve_nemo_bin(), smoke_test_transcription() (+2 more)

### Community 121 - "EnvSettings.jsx"
Cohesion: 0.29
Nodes (9): ALL_FIELDS, ColabGuide(), EnvField(), EnvSettings(), GROUPS, isSecretKey(), PROVIDER_CARDS, PROVIDER_CHOICES (+1 more)

### Community 122 - "lucide-react"
Cohesion: 0.29
Nodes (10): AccountPage(), fmt1(), PAYMENT_ISSUE_STATES, ApiKeysCard(), fmtNum(), postTitle(), postUrl(), postViews() (+2 more)

### Community 125 - "test_job_error_text.py"
Cohesion: 0.36
Nodes (4): _classify(), test_download_failure_survives_trailing_noise(), test_gemini_blip_is_not_blamed_on_ffmpeg(), test_silent_upload_reports_no_audio()

### Community 128 - "src/compositions/ShortVideo.tsx"
Cohesion: 0.27
Nodes (7): HookOverlay(), ShortVideo(), VideoEffects(), ShortVideoProps, shortVideoPropsSchema, DEFAULT_PROPS, RemotionRoot()

### Community 131 - "React + Vite"
Cohesion: 0.50
Nodes (3): Expanding the ESLint configuration, React Compiler, React + Vite

### Community 132 - "TestApplyCropOverrides"
Cohesion: 0.17
Nodes (3): fake_recut(), job(), TestApplyCropOverrides

### Community 133 - "ffmpeg_utils.py"
Cohesion: 0.22
Nodes (4): hwaccel_available(), nvenc_available(), _probe_hwaccel(), _probe_nvenc()

### Community 134 - "TestRangeMath"
Cohesion: 0.22
Nodes (4): rebase_segments(), within_range(), run_recut(), TestRangeMath

### Community 136 - "general_filtergraph"
Cohesion: 0.24
Nodes (3): general_filtergraph(), test_general_filtergraph_targets_output_geometry(), TestGeneralLayout

### Community 138 - "transcribe_media"
Cohesion: 0.22
Nodes (5): test_transcribe_media_goes_through_nemo(), test_transcribe_media_raises_on_silent_video(), _has_audio_stream(), NoAudioError, transcribe_media()

### Community 139 - "_EnvSemaphore"
Cohesion: 0.25
Nodes (4): test_env_semaphore_invalid_value_falls_back_to_one(), test_env_semaphore_picks_up_live_change(), test_env_semaphore_sizes_from_env(), _EnvSemaphore

### Community 144 - "add_hook_to_video"
Cohesion: 0.40
Nodes (3): add_hook_to_video(), auto_hook_clip(), run_hook()

### Community 145 - "PlanChoiceModal.jsx"
Cohesion: 0.67
Nodes (3): fmt(), PLAN_ORDER, PlanChoiceModal()

## Knowledge Gaps
- **5 isolated node(s):** `openshorts`, `fal.ai`, `Subject tracking stack (MediaPipe + YOLOv8)`, `Parakeet TDT 0.6B v3`, `Build-time SEO surface (vite-plugin-seo.js)`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 968 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **37 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `video_encode_args()` connect `video_encode_args` to `saasshorts.py`, `ffmpeg_utils.py`, `hooks.py`, `os`, `test_gemini_retry.py`, `typing`, `add_hook_to_video`, `main.py`, `run_pipeline`, `run_cut_concat`, `render`, `test_subtitles.py`, `subtitles.py`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **What connects `openshorts`, `fal.ai`, `Subject tracking stack (MediaPipe + YOLOv8)` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `asyncio` be split into smaller, more focused modules?**
  _Cohesion score 0.09425287356321839 - nodes in this community are weakly interconnected._
- **Why does `render()` connect `render` to `emphasis_times`, `video_encode_args`, `test_active_speaker.py`, `numpy`, `punch_in.py`, `general_filtergraph`, `crop_boxes`, `analyze_scene`, `main.py`, `screencast_layout.py`, `test_camera_inset.py`, `delivery_size`, `zoom_curve`, `hold`, `speaker_xs`?**
  _High betweenness centrality (0.012) - this node is a cross-community bridge._
- **Should `saasshorts.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08403361344537816 - nodes in this community are weakly interconnected._
- **Should `test_panel_layout.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06885245901639345 - nodes in this community are weakly interconnected._
- **Should `test_transcribe_backends.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09982174688057041 - nodes in this community are weakly interconnected._