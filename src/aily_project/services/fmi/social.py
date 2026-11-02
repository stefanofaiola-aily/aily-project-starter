"""Point-in-time Instagram windows, reviewed relevance and optional context."""

import re
from datetime import datetime, timedelta
from statistics import median
from zoneinfo import ZoneInfo

from .models import Inputs, Row, Snapshot, calendar_date, instant, number, truth
from .policy import Policy


def post_key(row: Row) -> str | None:
    post = row.get("post_id") or row.get("post_url")
    profile = row.get("profile_id") or row.get("profile_username")
    return f"{profile}:{post}" if post and profile else None


def observations(rows: list[Row], cutoff: datetime) -> tuple[list[Row], list[Row]]:
    """Filter captures BEFORE deduplication. Conflicting equal-time captures fail."""
    index: dict[str, Row] = {}
    evidence = []
    conflicts = set()
    for row in rows:
        ident, capture = post_key(row), instant(row.get("crawled_at"))
        if not ident or capture is None or capture > cutoff:
            evidence.append({**row, "historical_status": "late_or_unknown_capture"})
            continue
        old = index.get(ident)
        old_capture = instant(old.get("crawled_at")) if old else None
        if old_capture is None or capture > old_capture:
            index[ident] = row
            conflicts.discard(ident)
        elif capture == old_capture and row != old:
            conflicts.add(ident)
    for ident in conflicts:
        evidence.append(
            {**index.pop(ident), "historical_status": "conflicting_capture"}
        )
    return list(index.values()), evidence


def calculate(
    inputs: Inputs,
    snapshot: Snapshot,
    analysis: Row,
    entity: Row,
    cutoff: datetime | None,
    policy: Policy,
    *,
    simulation: bool = False,
) -> tuple[Row, list[Row], list[str]]:
    values: Row = {"social_platform": "instagram", "social_status": "unavailable"}
    reasons: list[str] = []
    dossier = analysis.get("calculation_mode") == "dossier"
    settings = analysis.get("dossier", {}).get("social", {}) if dossier else {}
    if dossier and settings.get("capture_cutoff"):
        configured_cutoff = instant(settings["capture_cutoff"])
        if cutoff is not None and configured_cutoff is not None:
            cutoff = min(cutoff, configured_cutoff)
    if dossier and settings.get("platform") != "instagram":
        return (
            {**values, "social_platform": settings.get("platform")},
            [],
            ["social:dossier_platform_not_in_current_extractor"],
        )
    if dossier and settings.get("aggregation"):
        return portfolio(inputs, snapshot, analysis, entity, cutoff, policy)
    score_metric = settings.get("metric", "likes")
    metric_column = {"likes": "like_count", "comments": "comment_count"}.get(
        score_metric
    )
    if metric_column is None:
        return values, [], ["social:unsupported_dossier_metric"]
    if (
        cutoff is None
        or not entity.get("handle")
        or (not simulation and not truth(entity.get("mapping_approved")))
        or (not simulation and not entity.get("evidence"))
        or not entity.get("profile_id")
    ):
        return values, [], ["social:missing_cutoff_or_reviewed_handle"]
    zone = ZoneInfo(str(analysis.get("timezone") or "UTC"))
    route = analysis.get("route")
    if route == "show":
        if not analysis.get("show_date"):
            return values, [], ["social:missing_show_date"]
        show = calendar_date(analysis["show_date"])
        current = [(show, show + timedelta(days=int(settings.get("current_days", 7))))]
        baseline = (
            [
                (
                    show - timedelta(days=int(settings.get("baseline_days", 15))),
                    show - timedelta(days=1),
                )
            ]
            if dossier
            else [
                (show - timedelta(days=30), show - timedelta(days=1)),
                (show + timedelta(days=8), show + timedelta(days=37)),
            ]
        )
        minimum = int(settings.get("min_posts", policy.show_min_posts))
    elif route == "annual" or (simulation and route == "period"):
        try:
            current = [
                (
                    calendar_date(analysis["current_start"]),
                    calendar_date(analysis["current_end"]),
                )
            ]
            baseline = [
                (
                    calendar_date(analysis["baseline_start"]),
                    calendar_date(analysis["baseline_end"]),
                )
            ]
        except (KeyError, ValueError, TypeError):
            return values, [], ["social:missing_annual_windows"]
        c, b = current[0], baseline[0]
        if (
            c[0] > c[1]
            or b[0] > b[1]
            or b[1] >= c[0]
            or abs((c[1] - c[0]).days - (b[1] - b[0]).days) > 2
            or not 350 <= (c[0] - b[0]).days <= 380
            or (not simulation and c[0].month != b[0].month)
            or (not simulation and c[1].month != b[1].month)
            or (not simulation and c[0].year != c[1].year)
            or (not simulation and b[0].year != b[1].year)
        ):
            return values, [], ["social:noncomparable_annual_windows"]
        minimum = int(settings.get("min_posts", policy.annual_min_posts))
    else:
        return values, [], ["social:analysis_route_required"]
    if max(e for _, e in current + baseline) > cutoff.astimezone(zone).date():
        return values, [], ["social:window_after_cutoff"]
    values["current_window"] = "; ".join(f"{s}/{e}" for s, e in current)
    values["baseline_window"] = "; ".join(f"{s}/{e}" for s, e in baseline)
    source = [
        r
        for r in snapshot.posts
        if str(r.get("profile_username", "")).lower().lstrip("@")
        == str(entity["handle"]).lower().lstrip("@")
        and (
            not entity.get("profile_id")
            or str(r.get("profile_id")) == str(entity["profile_id"])
        )
    ]
    retained, _ = observations(source, cutoff)
    reviews = {
        r["post_key"]: r
        for r in inputs.post_review
        if r.get("analysis_id") == analysis["analysis_id"]
    }
    posts = []
    samples: dict[str, list[Row]] = {"current": [], "baseline": []}
    for raw in retained:
        posted = instant(raw.get("date_posted"))
        if posted is None or posted > cutoff:
            continue  # unknown event time cannot become a historical app metric.
        captured_at = instant(raw.get("crawled_at"))
        if simulation and (captured_at is None or captured_at < posted):
            continue  # A capture cannot contain measurements of a future post.
        day = posted.astimezone(zone).date()
        if settings.get("months") and day.month not in settings["months"]:
            continue
        sample = next(
            (
                s
                for s, windows in (("current", current), ("baseline", baseline))
                if any(lo <= day <= hi for lo, hi in windows)
            ),
            None,
        )
        if sample is None:
            continue
        ident = post_key(raw)
        review = reviews.get(ident or "", {})
        reviewed = truth(review.get("reviewed")) and bool(review.get("evidence"))
        relevant = truth(review.get("relevant"))
        selected = reviewed or (simulation and not review)
        if simulation and not review:
            relevant = True  # Explicit show-window proxy, not a human decision.
            if dossier:
                caption = str(raw.get("caption") or "")
                pattern = (
                    settings.get("caption_pattern")
                    if sample == "current" and route == "show"
                    else settings.get("baseline_pattern")
                )
                relevant = (
                    bool(re.search(pattern, caption, re.I))
                    if pattern
                    else not (sample == "current" and route == "show")
                )
                excluded = settings.get("exclude_pattern")
                if excluded and re.search(excluded, caption, re.I):
                    relevant = False
        reason = "included"
        if not selected:
            reason = "relevance_unreviewed"
        elif route == "show" and sample == "current" and not relevant:
            reason = "not_collection_post"
        elif dossier and not relevant:
            reason = "excluded_by_dossier_relevance_rule"
        likes = number(raw.get(metric_column))
        if reason == "included" and (likes is None or likes < 0):
            reason = f"missing_{score_metric}"
        row = {
            **raw,
            "analysis_id": analysis["analysis_id"],
            "post_key": ident,
            "sample": sample,
            "posted_local_date": day,
            "reviewed": reviewed,
            "relevant": relevant,
            "inclusion_reason": reason,
            "historical_status": "dossier_retrospective_capture_not_replay"
            if dossier
            else "current_capture_simulation_not_replay"
            if simulation
            else "eligible",
            "selection_basis": "human_review"
            if reviewed
            else "business_dossier_caption_rule"
            if dossier
            else "simulation_window_proxy",
            "evidence": review.get("evidence"),
        }
        # Only reviewed measurements enter the app contract/supporting metrics.
        if not selected:
            for column in ("like_count", "comment_count", "video_view_count"):
                row[column] = None
        posts.append(row)
        if (
            selected
            and (not dossier or relevant)
            and (sample != "current" or route != "show" or relevant)
        ):
            samples[sample].append(row)
    months: dict[str, set[int]] = {}
    if route == "annual" and truth(
        settings.get("common_months_only", analysis.get("common_months_only"))
    ):
        sample_months = {
            sample: {
                r["posted_local_date"].month
                for r in rows
                if (likes := number(r.get(metric_column))) is not None and likes >= 0
            }
            for sample, rows in samples.items()
        }
        common = sample_months["current"] & sample_months["baseline"]
        for row in posts:
            if (
                row["posted_local_date"].month not in common
                and row["inclusion_reason"] == "included"
            ):
                row["inclusion_reason"] = "outside_common_months"
        samples = {
            sample: [r for r in rows if r["posted_local_date"].month in common]
            for sample, rows in samples.items()
        }
        values["social_month_selection"] = "common_calendar_months_only"
    else:
        values["social_month_selection"] = "all_posts_in_configured_windows"
    for sample in ("current", "baseline"):
        total = [r for r in posts if r["sample"] == sample]
        usable = [
            r
            for r in samples[sample]
            if (likes := number(r.get(metric_column))) is not None and likes >= 0
        ]
        months[sample] = {r["posted_local_date"].month for r in usable}
        values[f"{sample}_total_posts"] = len(total)
        values[f"{sample}_usable_posts"] = len(usable)
        values[f"{sample}_included_posts"] = len(usable)
        values[f"{sample}_excluded_posts"] = len(total) - len(usable)
        for metric, column in (
            ("likes", "like_count"),
            ("comments", "comment_count"),
            ("views", "video_view_count"),
        ):
            numbers = [
                n
                for r in samples[sample]
                if (n := number(r.get(column))) is not None and n >= 0
            ]
            values[f"{sample}_usable_{metric}"] = len(numbers)
            values[f"{sample}_median_{metric}"] = median(numbers) if numbers else None
        for fmt in ("image", "video", "carousel", "unknown"):
            values[f"{sample}_{fmt}_posts"] = sum(
                1
                for r in samples[sample]
                if str(r.get("post_type") or "unknown").lower() == fmt
            )
        values[f"{sample}_other_format_posts"] = sum(
            1
            for r in samples[sample]
            if str(r.get("post_type") or "unknown").lower()
            not in {"image", "video", "carousel", "unknown"}
        )
        for status in ("true", "false", "unknown"):
            values[f"{sample}_paid_{status}_posts"] = sum(
                1
                for r in samples[sample]
                if (
                    "unknown"
                    if r.get("is_paid_partnership") is None
                    else str(truth(r.get("is_paid_partnership"))).lower()
                )
                == status
            )
        if len(usable) < minimum:
            reasons.append(f"social:{sample}_requires_{minimum}_usable_posts")
    for metric in ("likes", "comments", "views"):
        cur, base = (
            values.get(f"current_median_{metric}"),
            values.get(f"baseline_median_{metric}"),
        )
        values[f"{metric}_lift"] = (
            cur / base - 1
            if cur is not None and base is not None and base > 0
            else None
        )
    values["common_months"] = len(months["current"] & months["baseline"])
    if route in {"annual", "period"} and values["common_months"] < int(
        settings.get("min_common_months", policy.annual_min_common_months)
    ):
        reasons.append("social:insufficient_common_months")
    if not simulation and not truth(analysis.get("social_coverage_reviewed")):
        reasons.append("social:coverage_unreviewed")
    if not simulation and any(not r["reviewed"] for r in posts):
        reasons.append("social:relevance_review_incomplete")
    values["relevance_review_status"] = (
        "complete" if all(r["reviewed"] for r in posts) and posts else "incomplete"
    )
    values["social_coverage_status"] = (
        "reviewed" if truth(analysis.get("social_coverage_reviewed")) else "unreviewed"
    )
    if simulation:
        values["relevance_review_status"] = (
            "business_dossier_rules_with_current_captures"
            if dossier
            else "simulation_window_proxy_not_human_reviewed"
        )
        values["social_coverage_status"] = (
            "observed_current_capture_archive_not_complete_census"
        )
    if dossier:
        values["social_scoring_metric"] = score_metric
    if values.get(f"{score_metric}_lift") is None:
        reasons.append(f"social:missing_or_zero_baseline_{score_metric}")
    if not reasons:
        values["social_score"] = max(
            0, min(100, 50 + 100 * values[f"{score_metric}_lift"])
        )
        values["social_status"] = "available"
    # Historical follower captures; never infer engagement rates.
    profiles = [
        r
        for r in snapshot.profiles
        if str(r.get("profile_username", "")).lower() == str(entity["handle"]).lower()
        and (
            not entity.get("profile_id")
            or str(r.get("profile_id")) == str(entity["profile_id"])
        )
    ]
    captures = [
        r
        for r in profiles
        if (stamp := instant(r.get("crawled_at"))) is not None
        and stamp <= cutoff
        and number(r.get("followers_count")) is not None
    ]

    def captured(row: Row) -> datetime:
        stamp = instant(row["crawled_at"])
        assert stamp is not None  # filtered above
        return stamp

    captures.sort(key=captured)
    if captures:
        latest = captures[-1]
        same_time = [r for r in captures if captured(r) == captured(latest)]
        if (
            len({(r.get("profile_id"), r.get("followers_count")) for r in same_time})
            == 1
        ):
            values.update(
                follower_count=number(latest["followers_count"]),
                follower_capture=latest["crawled_at"],
            )
            prior = [
                r
                for r in captures
                if r.get("profile_id") == latest.get("profile_id")
                and captured(r) < captured(latest)
            ]
            old_count = number(prior[-1].get("followers_count")) if prior else None
            new_count = number(latest.get("followers_count"))
            if (
                prior
                and len(
                    {
                        r.get("followers_count")
                        for r in prior
                        if captured(r) == captured(prior[-1])
                    }
                )
                > 1
            ):
                old_count = None
            if old_count is not None and old_count > 0 and new_count is not None:
                old = prior[-1]
                values.update(
                    prior_follower_count=number(old["followers_count"]),
                    prior_follower_capture=old["crawled_at"],
                    follower_growth=new_count / old_count - 1,
                )
    return values, posts, reasons


def portfolio(
    inputs: Inputs,
    snapshot: Snapshot,
    analysis: Row,
    entity: Row,
    cutoff: datetime | None,
    policy: Policy,
) -> tuple[Row, list[Row], list[str]]:
    """One lift per member; never pool differently sized accounts."""
    settings = analysis["dossier"]["social"]
    values: Row = {
        "social_platform": "instagram",
        "social_status": "unavailable",
        "social_scoring_metric": settings["metric"],
    }
    members = settings.get("members", [])
    if not members:
        return values, [], ["social:dossier_portfolio_member_parameters_missing"]
    lifts, used, excluded, posts = [], [], [], []
    metric = settings["metric"]
    for member in members:
        handle = member["handle"]
        ids = {
            str(r["profile_id"])
            for r in snapshot.posts
            if str(r.get("profile_username", "")).lower() == handle.lower()
            and r.get("profile_id")
        }
        profile = member.get("profile_id") or (
            next(iter(ids)) if len(ids) == 1 else None
        )
        child_settings = {
            k: v
            for k, v in settings.items()
            if k not in {"aggregation", "members", "min_members"}
        }
        child_settings.update(
            {k: member[k] for k in ("caption_pattern", "min_posts") if k in member}
        )
        child = {
            **analysis,
            **{
                k: v
                for k, v in member.items()
                if k
                in {
                    "route",
                    "timezone",
                    "show_date",
                    "current_start",
                    "current_end",
                    "baseline_start",
                    "baseline_end",
                }
            },
            "dossier": {**analysis["dossier"], "social": child_settings},
        }
        observed, selected, missing = calculate(
            inputs,
            snapshot,
            child,
            {**entity, "handle": handle, "profile_id": profile},
            cutoff,
            policy,
            simulation=True,
        )
        posts.extend({**p, "portfolio_member": member["name"]} for p in selected)
        if missing or observed.get(f"{metric}_lift") is None:
            excluded.append(f"{member['name']}: {'; '.join(missing)}")
            continue
        lifts.append(observed[f"{metric}_lift"])
        used.append(member["name"])
    values.update(
        social_used_members="; ".join(used),
        social_member_missing_reasons="; ".join(excluded),
        relevance_review_status="dossier_member_rules_with_current_captures",
        social_coverage_status="eligible_member_subset"
        if excluded
        else "all_selected_members_usable",
    )
    if len(lifts) < settings.get("min_members", len(members)):
        return values, posts, ["social:insufficient_eligible_portfolio_members"]
    values.update(
        {
            f"{metric}_lift": median(lifts),
            "social_score": max(0, min(100, 50 + 100 * median(lifts))),
            "social_status": "available",
        }
    )
    return values, posts, []
