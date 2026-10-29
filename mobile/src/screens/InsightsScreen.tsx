import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Image, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Button } from '../components/ui';
import { getAccountInsights, queueMetricsBackfill, regenerateInsightThemes, setComparisonExclusion } from '../services/api';
import { AccountInsightsData, TrackedPost } from '../types';

type SortKey = 'newest' | 'views' | 'reach' | 'engagement_rate' | 'shares' | 'saves' | 'comments';
type PerformancePost = AccountInsightsData['performance_posts'][number];

const metricValue = (value: number | null | undefined, rate = false) => value == null ? '—' : rate ? `${value.toFixed(1)}%` : value.toLocaleString();

export function InsightsScreen({ userId, onConnect }: { userId: string; onOpen: (post: TrackedPost) => void; onConnect: () => void }) {
  const [data, setData] = useState<AccountInsightsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [sort, setSort] = useState<SortKey>('views');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [methodologyOpen, setMethodologyOpen] = useState(false);
  const [missingOpen, setMissingOpen] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [saving, setSaving] = useState<string | null>(null);
  const [backfillNotice, setBackfillNotice] = useState('');

  const load = useCallback(async () => {
    setError('');
    try { setData(await getAccountInsights(userId)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not load insights.'); }
    finally { setLoading(false); }
  }, [userId]);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void load(); }, [load]);

  const regenerate = async () => { setLoading(true); try { await regenerateInsightThemes(userId); await load(); } finally { setLoading(false); } };
  const toggleExcluded = async (post: PerformancePost) => {
    if (!post.tracked_post_id) return;
    setSaving(post.tracked_post_id);
    try { await setComparisonExclusion(userId, post.tracked_post_id, !post.exclude_from_comparisons); await load(); }
    finally { setSaving(null); }
  };
  const fetchMissing = async () => {
    setBackfillNotice('');
    const result = await queueMetricsBackfill(userId);
    setBackfillNotice(result.queued ? `${result.queued} post(s) queued for background fetch.` : 'All eligible posts are queued or have metrics.');
  };

  if (loading && !data) return <View style={styles.state}><ActivityIndicator color="#7c3aed" /></View>;
  if (error && !data) return <View style={styles.state}><Text style={styles.empty}>{error}</Text><Button label="Try again" onPress={load} /><Button label="Reconnect Instagram" onPress={onConnect} secondary /></View>;

  const sorted = [...(data?.performance_posts ?? [])].sort((a, b) => sort === 'newest' ? new Date(b.published_at).getTime() - new Date(a.published_at).getTime() : (b.metrics?.[sort] ?? -1) - (a.metrics?.[sort] ?? -1));
  const metricPosts = sorted.filter((post) => post.has_metrics);
  const missingPosts = sorted.filter((post) => !post.has_metrics);
  const posts = showAll ? metricPosts : metricPosts.slice(0, 10);
  const summary = data?.performance_summary;
  const followerHours = data?.followers_online?.payload?.hourly_values ?? [];

  return <ScrollView refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />} contentContainerStyle={styles.content}>
    <Text style={styles.title}>Insights</Text>
    <View style={styles.card}>
      <View style={styles.rowBetween}><View><Text style={styles.section}>Account basis</Text><Text style={styles.label}>{data?.progress.patterns ?? 0} analyzed, {data?.progress.mature_posts ?? 0} mature</Text></View><Pressable onPress={() => setMethodologyOpen((value) => !value)} style={styles.smallButton}><Text style={styles.smallButtonText}>How this works</Text></Pressable></View>
      {methodologyOpen ? <View style={styles.info}><Text style={styles.label}>{data?.methodology.default_basis}</Text><Text style={styles.label}>{data?.methodology.pattern_rule}</Text></View> : null}
    </View>

    {followerHours.length === 24 ? <View style={styles.card}><Text style={styles.section}>When the audience is active</Text><Text style={styles.label}>Followers online · estimated from your screenshot</Text><Text style={styles.subTitle}>Top windows: {data?.followers_online?.top_windows?.map((item) => `${String(item.hour).padStart(2, '0')}:00`).join(', ') || 'unavailable'}</Text></View> : <View style={styles.card}><Text style={styles.subTitle}>When the audience is active · unavailable</Text><Text style={styles.label}>{data?.followers_online?.reason}</Text></View>}

    {data?.theme_stats.length ? <View style={styles.card}><View style={styles.rowBetween}><Text style={styles.section}>Account themes</Text><Pressable onPress={regenerate} style={styles.smallButton}><Text style={styles.smallButtonText}>Regenerate</Text></Pressable></View><View style={styles.tags}>{data.theme_stats.map((theme) => <Text key={theme.name} style={styles.tag}>{theme.name} · {theme.post_count} · {theme.median_views?.toLocaleString() ?? '—'} median views</Text>)}</View></View> : null}

    <View style={styles.card}>
      <View style={styles.rowBetween}><View style={styles.flex}><Text style={styles.section}>Post performance</Text><Text style={styles.label}>Instagram API lifetime metrics · mature same-format comparisons</Text></View><Pressable onPress={fetchMissing} style={styles.smallButton}><Text style={styles.smallButtonText}>Fetch metrics</Text></Pressable></View>
      {backfillNotice ? <Text style={styles.label}>{backfillNotice}</Text> : null}
      {summary ? <View style={styles.summaryGrid}>
        <Summary label="Typical" value={`${summary.reach_median.toLocaleString()} reach · ${summary.engagement_rate_median.toFixed(1)}% ER`} note={`reach n=${summary.reach_sample_size}; ER n=${summary.engagement_rate_sample_size}`} />
        <Summary label="Best reach" value={summary.highest_reach.value.toLocaleString()} note={new Date(summary.highest_reach.published_at).toLocaleDateString()} />
        <Summary label="Needs attention" value={summary.lowest_reach.value.toLocaleString()} note={summary.lowest_reach.note || 'Lowest observed reach in this mature format group.'} />
      </View> : null}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.sortRow}>{(['views', 'reach', 'engagement_rate', 'shares', 'saves', 'comments', 'newest'] as SortKey[]).map((key) => <Pressable key={key} onPress={() => setSort(key)} style={[styles.sort, sort === key && styles.sortActive]}><Text style={[styles.sortText, sort === key && styles.sortTextActive]}>{key.replaceAll('_', ' ')}</Text></Pressable>)}</ScrollView>
      {posts.map((post) => <PostRow key={post.tracked_post_id ?? post.instagram_media_id} post={post} open={expanded === (post.tracked_post_id ?? post.instagram_media_id)} onOpen={() => setExpanded(expanded === (post.tracked_post_id ?? post.instagram_media_id) ? null : (post.tracked_post_id ?? post.instagram_media_id))} onToggle={() => void toggleExcluded(post)} saving={saving === post.tracked_post_id} />)}
      {metricPosts.length > 10 ? <Pressable onPress={() => setShowAll((value) => !value)}><Text style={styles.link}>{showAll ? 'Show less' : `Show all ${metricPosts.length}`}</Text></Pressable> : null}
      {missingPosts.length ? <View style={styles.info}><Pressable onPress={() => setMissingOpen((value) => !value)}><Text style={styles.subTitle}>{missingPosts.length} posts without metrics</Text></Pressable>{missingOpen ? missingPosts.map((post) => <Text key={post.instagram_media_id} style={styles.label}>{post.display_title || 'Instagram post'} · {post.metrics_unavailable_reason}</Text>) : null}</View> : null}
    </View>

    {data?.patterns.length ? <View style={styles.card}><Text style={styles.section}>Content patterns</Text>{data.patterns.map((pattern) => <View key={`${pattern.category}-${pattern.label}`} style={styles.info}><Text style={styles.subTitle}>{pattern.category}: {pattern.label}</Text><Text style={styles.label}>{pattern.value.toFixed(1)}% vs {pattern.baseline.toFixed(1)}% ({pattern.posts} vs {pattern.comparison_posts ?? '—'} mature posts)</Text></View>)}<Text style={styles.label}>Observed difference, not a cause.</Text></View> : null}
  </ScrollView>;
}

function Summary({ label, value, note }: { label: string; value: string; note: string }) {
  return <View style={styles.summaryItem}><Text style={styles.metricLabel}>{label.toUpperCase()}</Text><Text style={styles.subTitle}>{value}</Text><Text style={styles.label}>{note}</Text></View>;
}

function PostRow({ post, open, onOpen, onToggle, saving }: { post: PerformancePost; open: boolean; onOpen: () => void; onToggle: () => void; saving: boolean }) {
  const metrics = post.metrics;
  return <View style={styles.post}><Pressable onPress={onOpen}><View style={styles.row}>{post.thumbnail_url ? <Image source={{ uri: post.thumbnail_url }} style={styles.thumbnail} /> : <View style={styles.thumbnail} />}<View style={styles.flex}><View style={styles.rowBetween}><Text style={styles.subTitle} numberOfLines={1}>{post.display_title || 'Instagram post'}</Text><Text style={styles.rank}>{post.comparison && post.comparison.group_size >= 6 ? `#${post.comparison.rank}` : '—'}</Text></View><Text style={styles.label}>{new Date(post.published_at).toLocaleDateString()} · {post.status_label}</Text></View></View><View style={styles.metrics}>{[['Views', metricValue(metrics?.views)], ['Reach', metricValue(metrics?.reach)], ['ER', metricValue(metrics?.engagement_rate, true)], ['Shares', metricValue(metrics?.shares)], ['Saves', metricValue(metrics?.saves)], ['Comments', metricValue(metrics?.comments)]].map(([label, value]) => <View key={label} style={styles.metricItem}><Text style={styles.metricLabel}>{label}</Text><Text style={styles.metricValue}>{value}</Text></View>)}</View></Pressable>{open ? <View style={styles.info}><Text style={styles.label}>{post.comparison_basis}</Text>{post.caption_excerpt ? <Text style={styles.label}>Caption: {post.caption_excerpt}</Text> : null}{post.tracked_post_id ? <Pressable disabled={saving} onPress={onToggle} style={styles.smallButton}><Text style={styles.smallButtonText}>{saving ? 'Saving…' : post.exclude_from_comparisons ? 'Include in comparisons' : 'Exclude from comparisons'}</Text></Pressable> : null}</View> : null}</View>;
}

const styles = StyleSheet.create({
  content: { padding: 20, paddingBottom: 32, gap: 14 }, state: { flex: 1, padding: 24, justifyContent: 'center', gap: 14 }, title: { fontSize: 30, lineHeight: 36, fontWeight: '800', color: '#201633' },
  card: { padding: 16, borderRadius: 18, backgroundColor: 'white', borderWidth: 1, borderColor: '#e7e0f0', gap: 10 }, section: { fontSize: 19, fontWeight: '800', color: '#201633' }, subTitle: { flexShrink: 1, fontWeight: '800', color: '#201633', lineHeight: 20 }, label: { color: '#746b82', fontSize: 12, lineHeight: 18 }, empty: { color: '#746b82', textAlign: 'center' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 }, rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 }, flex: { flex: 1 }, smallButton: { alignSelf: 'flex-start', borderRadius: 10, paddingVertical: 8, paddingHorizontal: 10, backgroundColor: '#eee8fa' }, smallButtonText: { color: '#5b21b6', fontSize: 11, fontWeight: '800' }, link: { color: '#5b21b6', fontWeight: '800', paddingVertical: 8 },
  info: { padding: 10, borderRadius: 10, backgroundColor: '#f7f5ff', gap: 6 }, tags: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 }, tag: { color: '#5b21b6', fontWeight: '700', fontSize: 12, backgroundColor: '#ede9fe', paddingVertical: 7, paddingHorizontal: 10, borderRadius: 20 },
  summaryGrid: { gap: 7 }, summaryItem: { padding: 10, borderRadius: 10, backgroundColor: '#f7f5ff', gap: 3 }, sortRow: { gap: 7, paddingVertical: 4 }, sort: { borderRadius: 16, paddingVertical: 7, paddingHorizontal: 10, backgroundColor: '#f3f0f8' }, sortActive: { backgroundColor: '#7c3aed' }, sortText: { color: '#5b5168', fontSize: 11, fontWeight: '700', textTransform: 'capitalize' }, sortTextActive: { color: 'white' },
  post: { borderTopWidth: 1, borderTopColor: '#eee8fa', paddingTop: 12, gap: 8 }, thumbnail: { width: 56, height: 56, borderRadius: 9, backgroundColor: '#eee8fa' }, rank: { color: '#5b21b6', fontWeight: '900' }, metrics: { marginTop: 10, flexDirection: 'row', flexWrap: 'wrap', gap: 6 }, metricItem: { width: '31%', padding: 7, borderRadius: 9, backgroundColor: '#f7f5ff' }, metricLabel: { color: '#746b82', fontSize: 9, textTransform: 'uppercase' }, metricValue: { color: '#201633', fontWeight: '800' },
});
