import { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Image, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { AiConsentModal } from "../components/AiConsentModal";
import { ApiError, getAccountInsights, grantAIProcessingConsent, refreshTrackedPost } from "../services/api";
import { AccountInsightsData, PerformancePost } from "../types";
import { UnifiedPicker } from "../components/UnifiedPicker";
import { colors } from "../theme/colors";

type SortKey = "views" | "reach" | "engagement_rate" | "shares" | "saves" | "comments" | "newest";
const sortKeys: SortKey[] = ["views", "reach", "engagement_rate", "shares", "saves", "comments", "newest"];
const sortName = (key: SortKey) => (key === "engagement_rate" ? "Engagement" : key[0].toUpperCase() + key.slice(1));
const sortOptions = sortKeys.map((value) => ({ value, label: sortName(value) }));
const number = (value?: number | null) => (value == null ? "–" : value.toLocaleString());
const rate = (value?: number | null) => (value == null ? "–" : `${value.toFixed(1)}%`);

export function InsightsScreen({
  accessToken,
  onOpen,
  onConnect,
}: {
  accessToken: string;
  onOpen: (trackedId: string) => void;
  onConnect: () => void;
}) {
  const [data, setData] = useState<AccountInsightsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sort, setSort] = useState<SortKey>("views");
  const [showAll, setShowAll] = useState(false);
  const [refreshing, setRefreshing] = useState<string | null>(null);
  const [cooldowns, setCooldowns] = useState<Record<string, boolean>>({});
  const [consentModalVisible, setConsentModalVisible] = useState(false);
  const [savingConsent, setSavingConsent] = useState(false);
  const load = useCallback(
    () =>
      getAccountInsights(accessToken)
        .then((next) => {
          setData(next);
          setError("");
        })
        .catch((reason) => {
          if (reason instanceof ApiError && reason.code === "consent_required") {
            setConsentModalVisible(true);
            setError("");
            return;
          }
          setError(reason instanceof Error ? reason.message : "Could not load insights.");
        })
        .finally(() => setLoading(false)),
    [accessToken],
  );
  useEffect(() => {
    void load();
  }, [load]);
  const posts = useMemo(() => {
    const result = [...(data?.performance_posts ?? [])];
    result.sort((a, b) =>
      sort === "newest"
        ? new Date(b.published_at).getTime() - new Date(a.published_at).getTime()
        : (b.metrics[sort] ?? -1) - (a.metrics[sort] ?? -1),
    );
    return result;
  }, [data, sort]);
  const refresh = async (post: PerformancePost) => {
    if (cooldowns[post.tracked_post_id]) return;
    setRefreshing(post.tracked_post_id);
    setError("");
    try {
      await refreshTrackedPost(accessToken, post.tracked_post_id);
      setCooldowns((current) => ({ ...current, [post.tracked_post_id]: true }));
      setTimeout(() => setCooldowns((current) => ({ ...current, [post.tracked_post_id]: false })), 60000);
      await load();
    } catch (reason) {
      if (reason instanceof ApiError && reason.code === "consent_required") setConsentModalVisible(true);
      else setError(reason instanceof Error ? reason.message : "Could not refresh this post.");
    } finally {
      setRefreshing(null);
    }
  };
  const acceptConsent = async () => {
    setSavingConsent(true);
    setError("");
    try {
      await grantAIProcessingConsent(accessToken);
      setConsentModalVisible(false);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save AI processing consent.");
    } finally {
      setSavingConsent(false);
    }
  };
  if (loading && !data)
    return (
      <>
        <View style={styles.state}>
          <ActivityIndicator color={colors.sky} />
        </View>
        <AiConsentModal
          visible={consentModalVisible}
          busy={savingConsent}
          onAccept={acceptConsent}
          onNotNow={() => setConsentModalVisible(false)}
        />
      </>
    );
  return (
    <>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>Insights</Text>
        {error ? (
          <View>
            <Text style={styles.error}>{error}</Text>
            {data?.sync_status === "reconnect_required" ? (
              <Pressable onPress={onConnect} style={styles.textButton}>
                <Text style={styles.link}>Reconnect Instagram</Text>
              </Pressable>
            ) : null}
          </View>
        ) : null}
        {data?.highlights.length === 4 ? (
          <View style={styles.highlights}>
            {data.highlights.map((item) => (
              <Pressable key={item.label} onPress={() => onOpen(item.tracked_post_id)} style={styles.highlight}>
                <Text style={styles.eyebrow}>{item.label}</Text>
                <View style={styles.highlightBody}>
                  {item.thumbnail_url ? (
                    <Image source={{ uri: item.thumbnail_url }} style={styles.highlightImage} />
                  ) : (
                    <View style={styles.highlightImage} />
                  )}
                  <View>
                    <Text style={styles.highlightValue}>
                      {item.metric === "engagement_rate" ? rate(item.value) : number(item.value)}
                    </Text>
                    <Text style={styles.muted}>{new Date(item.published_at).toLocaleDateString()}</Text>
                  </View>
                </View>
              </Pressable>
            ))}
          </View>
        ) : null}
        {data?.next_post_suggestion ? (
          <View style={styles.card}>
            <Text style={styles.section}>Next post suggestion</Text>
            <Text style={styles.body}>{data.next_post_suggestion}</Text>
          </View>
        ) : data?.next_post_suggestion_status === "pending" ? (
          <View style={styles.card}>
            <Text style={styles.section}>Next post suggestion</Text>
            <Text style={styles.muted}>Your suggestion is being prepared.</Text>
          </View>
        ) : data?.next_post_suggestion_status === "consent_required" ? (
          <View style={styles.card}>
            <Text style={styles.section}>Next post suggestion</Text>
            <Text style={styles.muted}>Enable optional AI processing to receive a next-post suggestion.</Text>
            <Pressable onPress={() => setConsentModalVisible(true)} style={styles.aiButton}>
              <Text style={styles.aiButtonText}>Review AI data use</Text>
            </Pressable>
          </View>
        ) : null}
        <View style={styles.card}>
          <View style={styles.postsHeader}>
            <Text style={styles.section}>Posts</Text>
            <UnifiedPicker
              label="Sort"
              title="Sort posts"
              options={sortOptions}
              value={sort}
              onChange={(next) => setSort(next as SortKey)}
              compact
            />
          </View>
          {(showAll ? posts : posts.slice(0, 5)).map((post) => (
            <PostRow
              key={post.tracked_post_id}
              post={post}
              onOpen={() => onOpen(post.tracked_post_id)}
              onRefresh={() => void refresh(post)}
              refreshing={refreshing === post.tracked_post_id}
              cooldown={Boolean(cooldowns[post.tracked_post_id])}
            />
          ))}
          {!showAll && posts.length > 5 ? (
            <Pressable onPress={() => setShowAll(true)} style={styles.showAll}>
              <Text style={styles.link}>Show all {posts.length}</Text>
            </Pressable>
          ) : null}
        </View>
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
function PostRow({
  post,
  onOpen,
  onRefresh,
  refreshing,
  cooldown,
}: {
  post: PerformancePost;
  onOpen: () => void;
  onRefresh: () => void;
  refreshing: boolean;
  cooldown: boolean;
}) {
  return (
    <Pressable onPress={onOpen} style={styles.postRow}>
      <Text style={styles.rank}>{post.rank ? `#${post.rank}` : "–"}</Text>
      {post.thumbnail_url ? (
        <Image source={{ uri: post.thumbnail_url }} style={styles.postImage} />
      ) : (
        <View style={styles.postImage} />
      )}
      <View style={styles.postMain}>
        <View style={styles.dateRow}>
          <Text style={styles.date}>{new Date(post.published_at).toLocaleDateString()}</Text>
          {post.needs_refresh ? (
            <Pressable
              disabled={refreshing || cooldown}
              onPress={(event) => {
                event.stopPropagation();
                onRefresh();
              }}
              style={styles.textButton}
            >
              <Text style={styles.link}>{refreshing ? "Refreshing…" : cooldown ? "Refreshed" : "Refresh"}</Text>
            </Pressable>
          ) : null}
        </View>
      </View>
      <View style={styles.postMetrics}>
        <Text style={styles.metricValue}>{number(post.metrics.views)}</Text>
        <Text style={styles.muted}>{rate(post.metrics.engagement_rate)}</Text>
      </View>
    </Pressable>
  );
}
const styles = StyleSheet.create({
  state: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.canvas },
  content: { padding: 16, paddingBottom: 32, gap: 14, backgroundColor: colors.canvas },
  title: { fontSize: 30, lineHeight: 40, fontWeight: "900", color: colors.ink },
  card: {
    padding: 16,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    gap: 14,
  },
  highlights: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  highlight: {
    width: "48%",
    minHeight: 128,
    padding: 13,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
  },
  eyebrow: {
    minHeight: 28,
    color: colors.muted,
    fontSize: 11,
    letterSpacing: 0.7,
    fontWeight: "900",
    textTransform: "uppercase",
  },
  highlightBody: { flexDirection: "row", alignItems: "center", gap: 8 },
  highlightImage: { width: 48, height: 48, borderRadius: 10, backgroundColor: colors.lineStrong },
  highlightValue: { color: colors.ink, fontSize: 19, fontWeight: "900" },
  muted: { color: colors.muted, fontSize: 12 },
  section: { color: colors.ink, fontSize: 20, fontWeight: "900" },
  body: { color: colors.ink, lineHeight: 21 },
  postsHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 10 },
  postRow: {
    minHeight: 76,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.line,
  },
  rank: { width: 28, fontWeight: "900", color: colors.ink },
  postImage: { width: 54, height: 54, borderRadius: 11, backgroundColor: colors.lineStrong },
  postMain: { flex: 1 },
  dateRow: { flexDirection: "row", alignItems: "center", gap: 4 },
  date: { fontWeight: "800", color: colors.ink },
  textButton: { minHeight: 44, justifyContent: "center", paddingHorizontal: 4 },
  link: { color: colors.primary, fontSize: 13, fontWeight: "700" },
  postMetrics: { width: 72, alignItems: "flex-end" },
  metricValue: { color: colors.ink, fontWeight: "900" },
  showAll: { minHeight: 44, alignItems: "center", justifyContent: "center" },
  error: { color: colors.muted, fontSize: 13 },
  aiButton: {
    alignSelf: "flex-start",
    minHeight: 42,
    justifyContent: "center",
    borderRadius: 12,
    paddingHorizontal: 14,
    backgroundColor: colors.primary,
  },
  aiButtonText: { color: colors.white, fontSize: 13, fontWeight: "800" },
});
