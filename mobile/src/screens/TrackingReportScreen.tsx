import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { getTrackedPost, getTrackedPosts, refreshTrackedPost } from '../services/api';
import { MetricKey, RangeRow, TrackedPost } from '../types';

const labels: Record<MetricKey, string> = { views: 'Views', reach: 'Reach', engagement_rate: 'Engagement', shares: 'Shares', saves: 'Saves', comments: 'Comments' };
const count = (value?: number | null) => value == null ? '–' : value.toLocaleString();
const rate = (value?: number | null) => value == null ? '–' : `${value.toFixed(1)}%`;
const display = (key: MetricKey, value?: number | null) => key === 'engagement_rate' ? rate(value) : count(value);

export function TrackingReportScreen({ userId, initial, onBack }: { userId: string; initial?: TrackedPost | null; onBack?: () => void }) {
  const [post, setPost] = useState<TrackedPost | null>(initial ?? null);
  const [posts, setPosts] = useState<TrackedPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [cooldown, setCooldown] = useState(false);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    setError('');
    try {
      if (post) setPost(await getTrackedPost(userId, post.tracking.id));
      else setPosts((await getTrackedPosts(userId)).items);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not load this post.'); }
    finally { setLoading(false); }
  // The full post object is intentionally excluded: only identity changes reload it.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [post?.tracking.id, userId]);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void load(); }, [load]);
  const refresh = async () => {
    if (!post || cooldown) return;
    setRefreshing(true); setError('');
    try { setPost(await refreshTrackedPost(userId, post.tracking.id)); setCooldown(true); setTimeout(() => setCooldown(false), 60000); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not refresh this post.'); }
    finally { setRefreshing(false); }
  };
  if (!post) return <ScrollView contentContainerStyle={styles.content}><Text style={styles.title}>Analyze</Text>{loading ? <ActivityIndicator color="#6D28D9" /> : posts.map((item) => <Pressable key={item.tracking.id} onPress={() => { setPost(item); setLoading(true); }} style={styles.card}><View style={styles.postChoice}>{item.media.thumbnail_url || item.media.media_url ? <Image source={{ uri: item.media.thumbnail_url || item.media.media_url }} style={styles.choiceImage} /> : <View style={styles.choiceImage} />}<Text numberOfLines={2} style={styles.choiceText}>{item.media.caption || 'Instagram post'}</Text></View></Pressable>)}</ScrollView>;
  const analysis = post.analysis;
  return <ScrollView contentContainerStyle={styles.content}>
    <View style={styles.titleRow}>{onBack ? <Pressable onPress={onBack} style={styles.back}><Text style={styles.backText}>‹</Text></Pressable> : null}<Text style={styles.title}>Analyze</Text></View>
    {error ? <Text style={styles.error}>{error}</Text> : null}
    {loading ? <ActivityIndicator color="#6D28D9" /> : <>
      <View style={styles.card}>
        <View style={styles.hero}>{post.media.thumbnail_url || post.media.media_url ? <Image source={{ uri: post.media.thumbnail_url || post.media.media_url }} style={styles.cover} /> : <View style={styles.cover} />}<View style={styles.heroText}><Text numberOfLines={1} style={styles.caption}>{post.media.caption || 'Instagram post'}</Text><Text style={styles.muted}>{new Date(post.media.published_at).toLocaleDateString()} · {analysis?.media_format ?? 'Post'} · {analysis?.age_days ?? 0} days</Text><Pressable disabled={refreshing || cooldown} onPress={refresh} style={styles.textButton}><Text style={styles.link}>{refreshing ? 'Refreshing…' : cooldown ? 'Refreshed' : 'Refresh metrics'}</Text></Pressable></View></View>
        <View style={styles.metrics}><Headline label="Reach" value={count(post.latest?.reach)} /><Headline label="Views" value={count(post.latest?.views)} /><Headline label="Engagement rate" value={rate(post.latest?.engagement_rate)} /></View>
      </View>
      {analysis?.summary ? <Card title="Summary"><Text style={styles.body}>{analysis.summary}</Text></Card> : null}
      {analysis?.comparable ? <>
        <View style={styles.findings}><Finding title="STANDS OUT" tone="positive" rows={analysis.stands_out} empty="Nothing above the usual range" /><Finding title="WEAKER" tone="weaker" rows={analysis.weaker} empty="Nothing below the usual range" /></View>
        <Card title="Usual range">{analysis.usual_ranges.map((row) => <Range key={row.metric} row={row} />)}</Card>
      </> : <View style={styles.card}><Text style={styles.muted}>Not enough comparable posts yet</Text></View>}
      {analysis ? <Card title="Audience comments"><Text style={styles.body}>{analysis.audience_comments.description ?? analysis.audience_comments.message}</Text></Card> : null}
    </>}
  </ScrollView>;
}
function Card({ title, children }: { title: string; children: React.ReactNode }) { return <View style={styles.card}><Text style={styles.section}>{title}</Text><View style={styles.cardBody}>{children}</View></View>; }
function Headline({ label, value }: { label: string; value: string }) { return <View style={styles.headline}><Text style={styles.headlineValue}>{value}</Text><Text style={styles.muted}>{label}</Text></View>; }
function Finding({ title, tone, rows, empty }: { title: string; tone: 'positive' | 'weaker'; rows: RangeRow[]; empty: string }) { return <View style={[styles.card, styles.finding]}><Text style={[styles.eyebrow, tone === 'positive' ? styles.positive : styles.weaker]}>{title}</Text>{rows.length ? rows.map((row) => <View key={row.metric} style={styles.findingRow}><Text style={styles.findingValue}>{labels[row.metric]}: {display(row.metric, row.value)}</Text><Text style={styles.muted}>usual {display(row.metric, row.usual_min)}–{display(row.metric, row.usual_max)}</Text></View>) : <Text style={styles.muted}>{empty}</Text>}</View>; }
function Range({ row }: { row: RangeRow }) { const color = row.status === 'above' ? '#15803D' : row.status === 'below' ? '#92400E' : '#6D28D9'; return <View style={styles.range}><Text style={styles.rangeLabel}>{row.metric === 'engagement_rate' ? 'Engage.' : labels[row.metric]}</Text><View style={styles.track}><View style={[styles.band, { left: `${row.band_start}%`, width: `${Math.max(2, row.band_end - row.band_start)}%` }]} /><View style={[styles.marker, { left: `${row.marker}%`, backgroundColor: color }]} /></View><Text style={styles.rangeValue}>{display(row.metric, row.value)} · {row.status === 'inside' ? `#${row.rank}` : row.status}</Text></View>; }

const styles = StyleSheet.create({
  content: { padding: 16, paddingBottom: 32, gap: 14, backgroundColor: '#F6F3FF' }, titleRow: { flexDirection: 'row', alignItems: 'center', gap: 12 }, title: { fontSize: 30, lineHeight: 40, fontWeight: '900', color: '#1E1633' }, back: { width: 44, height: 44, borderRadius: 12, backgroundColor: 'white', alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: '#E8E2FA' }, backText: { fontSize: 30, color: '#1E1633' }, card: { borderRadius: 16, borderWidth: 1, borderColor: '#E8E2FA', backgroundColor: 'white', padding: 16, gap: 12 }, hero: { flexDirection: 'row', gap: 12 }, cover: { width: 86, height: 86, borderRadius: 12, backgroundColor: '#D9D1F5' }, heroText: { flex: 1 }, caption: { fontWeight: '800', color: '#1E1633' }, muted: { color: '#5F587A', fontSize: 12 }, textButton: { minHeight: 44, justifyContent: 'flex-end', alignSelf: 'flex-start' }, link: { color: '#6D28D9', fontSize: 13, fontWeight: '700' }, metrics: { flexDirection: 'row', borderTopWidth: 1, borderTopColor: '#EEEAF9', paddingTop: 16 }, headline: { flex: 1 }, headlineValue: { fontSize: 24, fontWeight: '900', color: '#1E1633' }, section: { fontSize: 20, fontWeight: '900', color: '#1E1633' }, cardBody: { gap: 12 }, body: { color: '#1E1633', lineHeight: 21 }, findings: { gap: 14 }, finding: { flex: 1 }, eyebrow: { fontSize: 11, letterSpacing: .7, fontWeight: '900' }, positive: { color: '#166534' }, weaker: { color: '#92400E' }, findingRow: { flexDirection: 'row', justifyContent: 'space-between', gap: 8 }, findingValue: { color: '#1E1633', fontWeight: '800', fontSize: 13 }, range: { flexDirection: 'row', alignItems: 'center', gap: 8 }, rangeLabel: { width: 60, fontWeight: '700', color: '#1E1633' }, track: { flex: 1, height: 8, borderRadius: 4, backgroundColor: '#EEEAF9' }, band: { position: 'absolute', height: 8, borderRadius: 4, backgroundColor: '#C4B5FD' }, marker: { position: 'absolute', marginLeft: -7, top: -3, width: 14, height: 14, borderRadius: 7, borderWidth: 2, borderColor: 'white' }, rangeValue: { width: 88, textAlign: 'right', color: '#5F587A', fontSize: 12 }, error: { color: '#B91C1C' }, postChoice: { flexDirection: 'row', alignItems: 'center', gap: 12 }, choiceImage: { width: 64, height: 64, borderRadius: 12, backgroundColor: '#D9D1F5' }, choiceText: { flex: 1, fontWeight: '800', color: '#1E1633' },
});
