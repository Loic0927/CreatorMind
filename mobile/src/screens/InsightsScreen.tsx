import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Image, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { getAccountInsights, regenerateInsightThemes } from '../services/api';
import { AccountInsightsData, TrackedPost } from '../types';
import { Button } from '../components/ui';

type SortKey = 'newest' | 'views' | 'reach' | 'engagement_rate' | 'shares' | 'saves';

export function InsightsScreen({ userId, onConnect }: { userId: string; onOpen: (post: TrackedPost) => void; onConnect: () => void }) {
  const [data, setData] = useState<AccountInsightsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [sort, setSort] = useState<SortKey>('newest');
  const load = useCallback(async () => {
    setError('');
    try { setData(await getAccountInsights(userId)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not load insights.'); }
    finally { setLoading(false); }
  }, [userId]);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void load(); }, [load]);
  const regenerate = async () => { setLoading(true); try { await regenerateInsightThemes(userId); await load(); } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not regenerate themes.'); setLoading(false); } };
  if (loading && !data) return <View style={styles.state}><ActivityIndicator color="#7c3aed" /></View>;
  if (error && !data) return <View style={styles.state}><Text style={styles.empty}>{error}</Text><Button label="Try again" onPress={load} /><Button label="Reconnect Instagram" onPress={onConnect} secondary /></View>;
  const posts = [...(data?.performance_posts ?? [])].sort((a, b) => sort === 'newest' ? new Date(b.published_at).getTime() - new Date(a.published_at).getTime() : (b.metrics?.[sort] ?? -1) - (a.metrics?.[sort] ?? -1));
  const cap = data ? Math.min(data.progress.patterns, data.required_sample_size) : 0;
  return <ScrollView refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />} contentContainerStyle={styles.content}>
    <Text style={styles.title}>Insights</Text>
    <View style={styles.card}><Text style={styles.section}>Account basis</Text><Text style={styles.label}>{data?.sample_notice}</Text><Text style={styles.metric}>{cap}/{data?.required_sample_size}</Text>{data && data.progress.patterns > data.required_sample_size ? <Text style={styles.label}>{data.progress.patterns} analyzed posts total</Text> : null}<Text style={styles.label}>{data?.methodology.default_basis}</Text></View>
    <View style={styles.card}><View style={styles.row}><Text style={styles.section}>Account themes</Text><Pressable onPress={regenerate} style={styles.smallButton}><Text style={styles.smallButtonText}>Regenerate</Text></Pressable></View><Text style={styles.label}>{data?.theme_method}</Text><View style={styles.tags}>{data?.themes.map((theme) => <Text key={theme} style={styles.tag}>{theme}</Text>)}</View></View>
    <View style={styles.card}><Text style={styles.section}>Content patterns</Text>{data?.patterns.length ? data.patterns.map((pattern) => <View key={`${pattern.category}-${pattern.label}`} style={styles.pattern}><Text style={styles.subTitle}>{pattern.label} · {pattern.value}%</Text><Text style={styles.label}>{pattern.sample_note} · n={pattern.posts}</Text><Text style={styles.label}>{pattern.difference >= 0 ? '+' : ''}{pattern.difference} points vs {pattern.baseline}% · {pattern.basis}</Text></View>) : <Text style={styles.empty}>No clear content pattern yet</Text>}</View>
    <View style={styles.card}><Text style={styles.section}>Post performance</Text><Text style={styles.label}>Ranked only within the same format and maturity band.</Text><ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.sortRow}>{(['newest', 'views', 'reach', 'engagement_rate', 'shares', 'saves'] as SortKey[]).map((key) => <Pressable key={key} onPress={() => setSort(key)} style={[styles.sort, sort === key && styles.sortActive]}><Text style={[styles.sortText, sort === key && styles.sortTextActive]}>{key.replaceAll('_', ' ')}</Text></Pressable>)}</ScrollView>{posts.map((post) => <View key={post.tracked_post_id ?? post.instagram_media_id} style={styles.post}><View style={styles.row}>{post.thumbnail_url ? <Image source={{ uri: post.thumbnail_url }} style={styles.thumbnail} /> : <View style={styles.thumbnail} />}<View style={styles.flex}><Text style={styles.subTitle} numberOfLines={2}>{post.caption_excerpt || 'Instagram post'}</Text><Text style={styles.label}>{post.media_type_label} · {post.theme}</Text><Text style={styles.label}>{post.comparison_basis} · {post.age_days ?? '—'} days</Text></View></View><View style={styles.metrics}>{([['Views', post.metrics?.views], ['Reach', post.metrics?.reach], ['Engagement', post.metrics?.engagement_rate == null ? null : `${post.metrics.engagement_rate}%`], ['Shares', post.metrics?.shares], ['Saves', post.metrics?.saves]] as [string, string | number | null | undefined][]).map(([label, value]) => <View key={label} style={styles.metricCell}><Text style={styles.metricValue}>{value ?? '—'}</Text><Text style={styles.metricLabel}>{label}</Text></View>)}</View><Text style={styles.rank}>{post.comparison ? `#${post.comparison.rank} of ${post.comparison.group_size} by ${post.comparison.metric} · n=${post.comparison.group_size}` : 'Not ranked: no comparable group yet.'}</Text></View>)}</View>
  </ScrollView>;
}

const styles = StyleSheet.create({
  content: { padding: 20, paddingBottom: 32, gap: 14 }, state: { flex: 1, padding: 24, justifyContent: 'center', gap: 14 },
  title: { fontSize: 30, lineHeight: 36, fontWeight: '800', color: '#201633' }, card: { padding: 16, borderRadius: 18, backgroundColor: 'white', borderWidth: 1, borderColor: '#e7e0f0', gap: 10 },
  section: { fontSize: 19, fontWeight: '800', color: '#201633' }, subTitle: { fontWeight: '800', color: '#201633', lineHeight: 20 }, label: { color: '#746b82', fontSize: 12, lineHeight: 18 }, empty: { color: '#746b82', textAlign: 'center' }, metric: { fontSize: 24, fontWeight: '900', color: '#201633' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 }, flex: { flex: 1 }, smallButton: { marginLeft: 'auto', borderRadius: 10, paddingVertical: 8, paddingHorizontal: 10, backgroundColor: '#eee8fa' }, smallButtonText: { color: '#5b21b6', fontSize: 11, fontWeight: '800' },
  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 }, tag: { color: '#5b21b6', fontWeight: '700', fontSize: 12, backgroundColor: '#ede9fe', paddingVertical: 7, paddingHorizontal: 10, borderRadius: 20 },
  pattern: { padding: 12, borderRadius: 12, backgroundColor: '#f7f5ff', gap: 4 }, sortRow: { gap: 7, paddingVertical: 4 }, sort: { borderRadius: 16, paddingVertical: 7, paddingHorizontal: 10, backgroundColor: '#f3f0f8' }, sortActive: { backgroundColor: '#7c3aed' }, sortText: { color: '#5b5168', fontSize: 11, fontWeight: '700', textTransform: 'capitalize' }, sortTextActive: { color: 'white' },
  post: { borderTopWidth: 1, borderTopColor: '#eee8fa', paddingTop: 14, gap: 10 }, thumbnail: { width: 70, height: 70, borderRadius: 12, backgroundColor: '#eee8fa' }, metrics: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 }, metricCell: { width: '31%', padding: 8, borderRadius: 10, backgroundColor: '#f7f5ff' }, metricValue: { color: '#201633', fontWeight: '900' }, metricLabel: { color: '#746b82', fontSize: 9, textTransform: 'uppercase' }, rank: { color: '#047857', fontWeight: '700', fontSize: 11 },
});
