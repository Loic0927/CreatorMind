import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Image, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { AiConsentModal } from "../components/AiConsentModal";
import {
  ApiError,
  getTrackedPost,
  getTrackedPosts,
  grantAIProcessingConsent,
  refreshTrackedPost,
} from "../services/api";
import { MetricKey, NotComparableReason, RangeRow, TrackedPost } from "../types";
import { colors } from "../theme/colors";

const labels: Record<MetricKey, string> = {
  views: "Views",
  reach: "Reach",
  engagement_rate: "Engagement",
  shares: "Shares",
  saves: "Saves",
  comments: "Comments",
};
const count = (value?: number | null) => (value == null ? "–" : value.toLocaleString());
const rate = (value?: number | null) => (value == null ? "–" : `${value.toFixed(1)}%`);
const display = (key: MetricKey, value?: number | null) => (key === "engagement_rate" ? rate(value) : count(value));
const comparisonUnavailableMessage = (reason?: NotComparableReason | null) => {
  if (reason === "too_early") return "Too early to compare — check back later.";
  if (reason === "too_few_posts") return "Track more posts in this format to compare.";
  return "Not enough comparable posts yet.";
};

export function TrackingReportScreen({
  accessToken,
  initial,
  onBack,
}: {
  accessToken: string;
  initial?: TrackedPost | null;
  onBack?: () => void;
}) {
  const [post, setPost] = useState<TrackedPost | null>(initial ?? null);
  const [posts, setPosts] = useState<TrackedPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [cooldown, setCooldown] = useState(false);
  const [showComments, setShowComments] = useState(false);
  const [consentModalVisible, setConsentModalVisible] = useState(false);
  const [savingConsent, setSavingConsent] = useState(false);
  const [error, setError] = useState("");
  const postId = post?.tracking.id;
  const load = useCallback(
    () =>
      (postId
        ? getTrackedPost(accessToken, postId).then(setPost)
        : getTrackedPosts(accessToken).then(({ items }) => setPosts(items))
      )
        .then(() => setError(""))
        .catch((reason) => setError(reason instanceof Error ? reason.message : "Could not load this post."))
        .finally(() => setLoading(false)),
    [postId, accessToken],
  );
  useEffect(() => {
    void load();
  }, [load]);
  const refreshMetrics = async () => {
    if (!post || cooldown) return;
    setRefreshing(true);
    setError("");
    try {
      setPost(await refreshTrackedPost(accessToken, post.tracking.id));
      setCooldown(true);
      setTimeout(() => setCooldown(false), 60000);
    } catch (reason) {
      if (reason instanceof ApiError && reason.code === "consent_required") setConsentModalVisible(true);
      else setError(reason instanceof Error ? reason.message : "Could not refresh this post.");
    } finally {
      setRefreshing(false);
    }
  };
  const acceptConsent = async () => {
    setSavingConsent(true);
    try {
      await grantAIProcessingConsent(accessToken);
      setConsentModalVisible(false);
      await refreshMetrics();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save AI processing consent.");
    } finally {
      setSavingConsent(false);
    }
  };
  if (!post)
    return (
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>Analyze</Text>
        {loading ? (
          <ActivityIndicator color={colors.sky} />
        ) : (
          posts.map((item) => (
            <Pressable
              key={item.tracking.id}
              onPress={() => {
                setPost(item);
                setLoading(true);
              }}
              style={styles.card}
            >
              <View style={styles.postChoice}>
                {item.media.thumbnail_url || item.media.media_url ? (
                  <Image
                    source={{ uri: item.media.thumbnail_url || item.media.media_url }}
                    style={styles.choiceImage}
                  />
                ) : (
                  <View style={styles.choiceImage} />
                )}
                <Text numberOfLines={2} style={styles.choiceText}>
                  {item.media.caption || "Instagram post"}
                </Text>
              </View>
            </Pressable>
          ))
        )}
      </ScrollView>
    );
  const analysis = post.analysis;
  return (
    <>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.titleRow}>
          {onBack ? (
            <Pressable onPress={onBack} style={styles.back}>
              <Text style={styles.backText}>‹</Text>
            </Pressable>
          ) : null}
          <Text style={styles.title}>Analyze</Text>
        </View>
        {error ? <Text style={styles.error}>{error}</Text> : null}
        {loading ? (
          <ActivityIndicator color={colors.sky} />
        ) : (
          <>
            <View style={styles.card}>
              <View style={styles.hero}>
                {post.media.thumbnail_url || post.media.media_url ? (
                  <Image source={{ uri: post.media.thumbnail_url || post.media.media_url }} style={styles.cover} />
                ) : (
                  <View style={styles.cover} />
                )}
                <View style={styles.heroText}>
                  <Text numberOfLines={1} style={styles.caption}>
                    {post.media.caption || "Instagram post"}
                  </Text>
                  <Text style={styles.muted}>
                    {new Date(post.media.published_at).toLocaleDateString()} · {analysis?.media_format ?? "Post"} ·{" "}
                    {analysis?.age_days ?? 0} days
                  </Text>
                  <Pressable disabled={refreshing || cooldown} onPress={refreshMetrics} style={styles.textButton}>
                    <Text style={styles.link}>
                      {refreshing ? "Refreshing…" : cooldown ? "Refreshed" : "Refresh metrics"}
                    </Text>
                  </Pressable>
                </View>
              </View>
              <View style={styles.metrics}>
                <Headline label="Reach" value={count(post.latest?.reach)} />
                <Headline label="Views" value={count(post.latest?.views)} />
                <Headline label="Engagement rate" value={rate(post.latest?.engagement_rate)} />
              </View>
            </View>
            {analysis?.summary ? (
              <Card title="Summary">
                <Text style={styles.body}>{analysis.summary}</Text>
              </Card>
            ) : analysis?.summary_status === "pending" ? (
              <Card title="Summary">
                <Text style={styles.muted}>Your summary is being prepared.</Text>
              </Card>
            ) : null}
            {analysis?.comparable ? (
              <>
                <View style={styles.findings}>
                  <Finding
                    title="STANDS OUT"
                    tone="positive"
                    rows={analysis.stands_out}
                    empty="Nothing above the usual range"
                  />
                  <Finding title="WEAKER" tone="weaker" rows={analysis.weaker} empty="Nothing below the usual range" />
                </View>
                <Card title="Usual range">
                  {analysis.usual_ranges.map((row) => (
                    <Range key={row.metric} row={row} />
                  ))}
                </Card>
              </>
            ) : (
              <View style={styles.card}>
                <Text style={styles.muted}>{comparisonUnavailableMessage(analysis?.not_comparable_reason)}</Text>
              </View>
            )}
            {analysis ? (
              <Card title="Audience comments">
                <Text style={styles.body}>
                  {analysis.audience_comments.description ??
                    analysis.audience_comments.message ??
                    "Audience comments are not available yet."}
                </Text>
                {analysis.audience_comments.state === "consent_required" ? (
                  <Pressable onPress={() => setConsentModalVisible(true)} style={styles.aiButton}>
                    <Text style={styles.aiButtonText}>Review AI data use</Text>
                  </Pressable>
                ) : null}
                {analysis.audience_comments.items?.length ? (
                  <>
                    <Pressable
                      accessibilityRole="button"
                      accessibilityState={{ expanded: showComments }}
                      onPress={() => setShowComments((current) => !current)}
                      style={styles.commentsToggle}
                    >
                      <Text style={styles.link}>
                        {showComments ? "Hide comments" : `Show comments (${analysis.audience_comments.items.length})`}
                      </Text>
                    </Pressable>
                    {showComments ? (
                      <View style={styles.commentsList}>
                        {analysis.audience_comments.items.map((comment) => (
                          <View key={`${comment.timestamp}-${comment.text}`} style={styles.comment}>
                            <Text style={styles.body}>{comment.text}</Text>
                            <Text style={styles.muted}>
                              {new Date(comment.timestamp).toLocaleDateString()} · {comment.like_count}{" "}
                              {comment.like_count === 1 ? "like" : "likes"}
                            </Text>
                          </View>
                        ))}
                      </View>
                    ) : null}
                  </>
                ) : null}
              </Card>
            ) : null}
          </>
        )}
      </ScrollView>
      <AiConsentModal
        visible={consentModalVisible}
        busy={savingConsent}
        onAccept={acceptConsent}
        onNotNow={() => setConsentModalVisible(false)}
      />
    </>
  );
}
function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.card}>
      <Text style={styles.section}>{title}</Text>
      <View style={styles.cardBody}>{children}</View>
    </View>
  );
}
function Headline({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.headline}>
      <Text style={styles.headlineValue}>{value}</Text>
      <Text style={styles.muted}>{label}</Text>
    </View>
  );
}
function Finding({
  title,
  tone,
  rows,
  empty,
}: {
  title: string;
  tone: "positive" | "weaker";
  rows: RangeRow[];
  empty: string;
}) {
  return (
    <View style={[styles.card, styles.finding]}>
      <Text style={[styles.eyebrow, tone === "positive" ? styles.positive : styles.weaker]}>{title}</Text>
      {rows.length ? (
        rows.map((row) => (
          <View key={row.metric} style={styles.findingRow}>
            <Text style={styles.findingValue}>
              {labels[row.metric]}: {display(row.metric, row.value)}
            </Text>
            <Text style={styles.muted}>
              usual {display(row.metric, row.usual_min)}–{display(row.metric, row.usual_max)}
            </Text>
          </View>
        ))
      ) : (
        <Text style={styles.muted}>{empty}</Text>
      )}
    </View>
  );
}
function Range({ row }: { row: RangeRow }) {
  const color = row.status === "above" ? "#15803D" : row.status === "below" ? "#92400E" : colors.primary;
  return (
    <View style={styles.range}>
      <Text style={styles.rangeLabel}>{row.metric === "engagement_rate" ? "Engage." : labels[row.metric]}</Text>
      <View style={styles.track}>
        <View
          style={[styles.band, { left: `${row.band_start}%`, width: `${Math.max(2, row.band_end - row.band_start)}%` }]}
        />
        <View style={[styles.marker, { left: `${row.marker}%`, backgroundColor: color }]} />
      </View>
      <Text style={styles.rangeValue}>
        {display(row.metric, row.value)} · {row.status === "inside" ? `#${row.rank}` : row.status}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { padding: 16, paddingBottom: 32, gap: 14, backgroundColor: colors.canvas },
  titleRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  title: { fontSize: 30, lineHeight: 40, fontWeight: "900", color: colors.ink },
  back: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.line,
  },
  backText: { fontSize: 30, color: colors.ink },
  card: {
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    padding: 16,
    gap: 12,
  },
  hero: { flexDirection: "row", gap: 12 },
  cover: { width: 86, height: 86, borderRadius: 12, backgroundColor: colors.lineStrong },
  heroText: { flex: 1 },
  caption: { fontWeight: "800", color: colors.ink },
  muted: { color: colors.muted, fontSize: 12 },
  textButton: { minHeight: 44, justifyContent: "flex-end", alignSelf: "flex-start" },
  link: { color: colors.primary, fontSize: 13, fontWeight: "700" },
  metrics: { flexDirection: "row", borderTopWidth: 1, borderTopColor: colors.line, paddingTop: 16 },
  headline: { flex: 1 },
  headlineValue: { fontSize: 24, fontWeight: "900", color: colors.ink },
  section: { fontSize: 20, fontWeight: "900", color: colors.ink },
  cardBody: { gap: 12 },
  body: { color: colors.ink, lineHeight: 21 },
  findings: { gap: 14 },
  finding: { flex: 1 },
  eyebrow: { fontSize: 11, letterSpacing: 0.7, fontWeight: "900" },
  positive: { color: "#166534" },
  weaker: { color: "#92400E" },
  findingRow: { flexDirection: "row", justifyContent: "space-between", gap: 8 },
  findingValue: { color: colors.ink, fontWeight: "800", fontSize: 13 },
  range: { flexDirection: "row", alignItems: "center", gap: 8 },
  rangeLabel: { width: 60, fontWeight: "700", color: colors.ink },
  track: { flex: 1, height: 8, borderRadius: 4, backgroundColor: colors.subtle },
  band: { position: "absolute", height: 8, borderRadius: 4, backgroundColor: colors.lineStrong },
  marker: {
    position: "absolute",
    marginLeft: -7,
    top: -3,
    width: 14,
    height: 14,
    borderRadius: 7,
    borderWidth: 2,
    borderColor: colors.surface,
  },
  rangeValue: { width: 88, textAlign: "right", color: colors.muted, fontSize: 12 },
  error: { color: colors.danger },
  postChoice: { flexDirection: "row", alignItems: "center", gap: 12 },
  choiceImage: { width: 64, height: 64, borderRadius: 12, backgroundColor: colors.lineStrong },
  choiceText: { flex: 1, fontWeight: "800", color: colors.ink },
  aiButton: {
    alignSelf: "flex-start",
    minHeight: 42,
    justifyContent: "center",
    borderRadius: 12,
    paddingHorizontal: 14,
    backgroundColor: colors.primary,
  },
  aiButtonText: { color: colors.white, fontSize: 13, fontWeight: "800" },
  commentsToggle: { alignSelf: "flex-start", minHeight: 42, justifyContent: "center" },
  commentsList: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.line },
  comment: { gap: 4, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.line, paddingVertical: 12 },
});
