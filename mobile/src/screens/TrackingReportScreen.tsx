import { useCallback, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { ActivityIndicator, Alert, Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Button } from '../components/ui';
import { analyzeTrackedPost, getTrackedPost, refreshTrackedPost, stopTracking } from '../services/api';
import { PostAnalysis, TrackedPost } from '../types';

export function TrackingReportScreen({ userId, initial, onBack }: { userId: string; initial: TrackedPost; onBack: () => void }) {
  const [post, setPost] = useState(initial);
  const [working, setWorking] = useState<'refresh' | 'analyze' | null>(null);
  const [viewingAnalysisId, setViewingAnalysisId] = useState('');
  const load = useCallback(async () => {
    setPost(await getTrackedPost(userId, initial.tracking.id));
  }, [initial.tracking.id, userId]);

  // The state update happens after the asynchronous API request.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void load(); }, [load]);

  const refresh = async () => {
    setWorking('refresh');
    try {
      await refreshTrackedPost(userId, post.tracking.id);
      await load();
    } catch (error) {
      Alert.alert('Refresh unavailable', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setWorking(null);
    }
  };
  const analyze = async () => {
    setWorking('analyze');
    try {
      const result = await analyzeTrackedPost(userId, post.tracking.id);
      setViewingAnalysisId(result.id);
      await load();
    } catch (error) {
      Alert.alert('Analysis unavailable', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setWorking(null);
    }
  };
  const stop = () => Alert.alert(
    'Stop tracking?',
    'Historical snapshots and analyses will be kept, but this post will no longer sync.',
    [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Stop tracking', style: 'destructive', onPress: async () => { await stopTracking(userId, post.tracking.id); onBack(); } },
    ],
  );

  const image = post.media.thumbnail_url || post.media.media_url;
  const latest = post.latest;
  const displayedAnalysis = post.analyses?.find((item) => item.id === viewingAnalysisId) ?? post.analyses?.[0];
  return (
    <ScrollView contentContainerStyle={styles.content}>
      <Text style={styles.title}>Post analysis</Text>
      {image ? <Image source={{ uri: image }} style={styles.image} /> : <View style={styles.image} />}
      <Text style={styles.date}>{new Date(post.media.published_at).toLocaleString()}</Text>
      <Text style={styles.caption}>{post.media.caption || 'No caption'}</Text>

      <Text style={styles.section}>Observed metrics</Text>
      <View style={styles.metrics}>
        {[
          ['Likes', latest?.likes],
          ['Comments', latest?.comments],
          ['Saves', latest?.saves],
          ['Shares', latest?.shares],
          ['Reach', latest?.reach],
          ['Views', latest?.views],
          ['Engagement rate', latest?.engagement_rate == null ? null : `${latest.engagement_rate}%`],
        ].map(([label, value]) => (
          <View key={String(label)} style={styles.metric}>
            <Text style={styles.value}>{value ?? '—'}</Text>
            <Text style={styles.label}>{label}</Text>
          </View>
        ))}
      </View>
      <Text style={styles.label}>Last updated {latest ? new Date(latest.captured_at).toLocaleString() : '—'}</Text>
      {working && <ActivityIndicator color="#7c3aed" />}
      <View style={styles.actions}>
        <View style={styles.action}><Button label={working === 'refresh' ? 'Refreshing…' : 'Refresh metrics'} onPress={refresh} disabled={working !== null} secondary /></View>
        <View style={styles.action}><Button label={working === 'analyze' ? 'Analyzing…' : 'Analyze post'} onPress={analyze} disabled={working !== null || !latest} /></View>
      </View>

      {displayedAnalysis ? <AnalysisPanel analysis={displayedAnalysis} /> : (
        <View style={styles.emptyAnalysis}>
          <Text style={styles.emptyTitle}>No saved analysis yet</Text>
          <Text style={styles.label}>Refresh the metrics, then analyze this post using its real content and performance.</Text>
        </View>
      )}

      <Text style={styles.section}>Analysis history</Text>
      {post.analyses?.length ? post.analyses.map((analysis) => (
        <Pressable key={analysis.id} onPress={() => setViewingAnalysisId(analysis.id)} style={[styles.history, displayedAnalysis?.id === analysis.id && styles.historySelected]}>
          <Text style={styles.historySummary}>{analysis.output_payload.score ? `Score ${analysis.output_payload.score.overall} · Grade ${analysis.output_payload.score.grade}` : 'Legacy analysis'}</Text>
          <Text style={styles.label}>{new Date(analysis.created_at).toLocaleString()}</Text>
          {analysis.output_payload.risks?.some((item) => item.toLowerCase().includes('stalled')) && <Text style={styles.riskText}>Growth plateau detected</Text>}
        </Pressable>
      )) : <Text style={styles.label}>No analysis history yet.</Text>}

      <Text style={styles.section}>Snapshot history</Text>
      {post.snapshots?.length ? post.snapshots.map((snapshot) => (
        <View key={snapshot.id} style={styles.snapshot}>
          <Text>{new Date(snapshot.captured_at).toLocaleString()}</Text>
          <Text style={styles.label}>Reach {snapshot.reach ?? '—'} · Engagement {snapshot.engagement_rate}%</Text>
        </View>
      )) : <Text style={styles.label}>No snapshot history yet.</Text>}

      <Button label="Stop tracking" onPress={stop} secondary />
      <Button label="Back" onPress={onBack} secondary />
    </ScrollView>
  );
}

function AnalysisPanel({ analysis }: { analysis: PostAnalysis }) {
  const output = analysis.output_payload;
  if (!output.score) return <View style={styles.emptyAnalysis}><Text style={styles.emptyTitle}>Legacy analysis</Text><Text style={styles.label}>{output.summary ?? 'Run a new analysis to view the creator intelligence dashboard.'}</Text></View>;
  return (
    <View style={styles.dashboard}>
      <View style={styles.scoreCard}><Text style={styles.eyebrow}>POST SCORE</Text><Text style={styles.score}>{output.score.overall}<Text style={styles.scoreOutOf}> / 100</Text></Text><Text style={styles.grade}>Grade {output.score.grade}</Text>
        {Object.entries(output.score.categories).map(([name, value]) => <View key={name} style={styles.scoreRow}><Text style={styles.scoreLabel}>{name}</Text><View style={styles.scoreTrack}><View style={[styles.scoreFill, { width: `${value}%`, backgroundColor: value >= 75 ? '#10b981' : value >= 50 ? '#f59e0b' : '#ef4444' }]} /></View><Text style={styles.scoreNumber}>{value}</Text></View>)}
      </View>
      <Panel title="Top insights">{output.top_insights?.map((item) => <Text key={item.text} style={styles.panelText}>{item.status === 'strong' ? '✅' : item.status === 'attention' ? '⚠️' : 'ℹ️'} {item.text}</Text>)}</Panel>
      <Panel title="Why it worked">{output.why_it_worked?.map((item) => <View key={item.factor} style={styles.subcard}><Text style={styles.subcardTitle}>{item.factor} · {item.estimated_impact}</Text><Text style={styles.label}>{item.explanation}</Text></View>)}</Panel>
      <Panel title="Compared with your average"><View style={styles.benchmarkGrid}>{output.benchmarks?.filter((item) => item.current != null).map((item) => <View key={item.metric} style={styles.benchmark}><Text style={styles.analysisLabel}>{item.metric.replaceAll('_', ' ')}</Text><Text style={styles.benchmarkValue}>{item.current}</Text><Text style={[styles.label, item.percent_change != null && item.percent_change >= 0 ? styles.positive : styles.negative]}>{item.percent_change == null ? 'More posts needed' : `${item.percent_change >= 0 ? '↑' : '↓'} ${Math.abs(item.percent_change)}% ${item.direction} average`}</Text></View>)}</View></Panel>
      <Panel title="Risks">{output.risks?.length ? output.risks.map((item) => <Text key={item} style={styles.riskText}>⚠️ {item}</Text>) : <Text style={styles.label}>No evidence-backed risk detected.</Text>}</Panel>
      <Panel title="Next post recommendations">{output.recommendations.map((item, index) => typeof item === 'string' ? <Text key={item} style={styles.panelText}>{item}</Text> : <View key={`${item.action}-${index}`} style={styles.subcard}><Text style={styles.subcardTitle}>{item.action}</Text><Text style={styles.label}>Reason: {item.reason}</Text><Text style={styles.impact}>Expected impact: {item.expected_impact}</Text></View>)}</Panel>
      <Panel title={`AI confidence · ${output.confidence?.score ?? 0}%`}>{output.confidence?.inputs.map((item) => <Text key={item.name} style={styles.panelText}>{item.available ? '✅' : '❌'} {item.name}{item.detail ? ` · ${item.detail}` : ''}</Text>)}</Panel>
      <Panel title="Content pattern winners">{output.content_patterns?.length ? output.content_patterns.map((item) => <View key={item.pattern} style={styles.subcard}><Text style={styles.subcardTitle}>{item.pattern} · {item.average_score}</Text><Text style={styles.label}>{item.sample_size} post{item.sample_size === 1 ? '' : 's'} · {item.difference_from_baseline >= 0 ? '+' : ''}{item.difference_from_baseline} vs baseline</Text></View>) : <Text style={styles.label}>Track more posts to detect repeatable formats.</Text>}</Panel>
    </View>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) { return <View style={styles.panel}><Text style={styles.panelTitle}>{title}</Text><View style={styles.panelBody}>{children}</View></View>; }

const styles = StyleSheet.create({
  content: { padding: 20, paddingBottom: 32, gap: 14 },
  title: { fontSize: 30, lineHeight: 36, fontWeight: '800', color: '#201633' },
  image: { width: '100%', aspectRatio: 1.2, borderRadius: 18, backgroundColor: '#eee8fa' },
  date: { color: '#746b82' },
  caption: { color: '#201633', lineHeight: 21 },
  metrics: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  metric: { width: '30%', padding: 10, borderRadius: 12, backgroundColor: 'white' },
  value: { fontWeight: '800', color: '#201633' },
  label: { color: '#746b82', fontSize: 12, lineHeight: 18 },
  section: { fontSize: 19, fontWeight: '800', color: '#201633', marginTop: 6 },
  actions: { flexDirection: 'row', gap: 10 },
  action: { flex: 1 },
  emptyAnalysis: { padding: 16, gap: 5, borderRadius: 16, backgroundColor: 'white' },
  emptyTitle: { fontWeight: '800', color: '#201633' },
  snapshot: { padding: 12, borderRadius: 12, backgroundColor: 'white', gap: 4 },
  history: { padding: 14, borderRadius: 14, backgroundColor: 'white', gap: 5 },
  historySelected: { borderWidth: 2, borderColor: '#8b5cf6' },
  historySummary: { color: '#201633', fontWeight: '700', lineHeight: 20 },
  snapshotId: { color: '#6d28d9', fontSize: 11, fontWeight: '700' },
  analysis: { gap: 14, padding: 18, borderRadius: 20, backgroundColor: '#24163b' },
  eyebrow: { color: '#c4b5fd', fontSize: 11, fontWeight: '800', letterSpacing: 1.2 },
  analysisSummary: { color: 'white', fontSize: 17, lineHeight: 25, fontWeight: '700' },
  analysisMetrics: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  analysisMetric: { width: '30%', padding: 10, borderRadius: 12, backgroundColor: '#ffffff14' },
  analysisValue: { color: 'white', fontWeight: '900' },
  analysisLabel: { color: '#d9d0e5', fontSize: 9, textTransform: 'uppercase' },
  delta: { color: '#c4b5fd', fontSize: 10, marginTop: 3 },
  analysisList: { gap: 5 },
  analysisTitle: { color: '#c4b5fd', fontWeight: '800' },
  analysisItem: { color: '#eee8f6', lineHeight: 20 },
  analysisMuted: { color: '#d9d0e5', fontSize: 12 },
  source: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: '#ffffff22', paddingTop: 12, color: '#c4b5fd', fontSize: 10 },
  dashboard: { gap: 14 },
  scoreCard: { gap: 10, padding: 18, borderRadius: 20, backgroundColor: '#24163b' },
  score: { color: 'white', fontSize: 42, fontWeight: '900' },
  scoreOutOf: { color: '#c4b5fd', fontSize: 17 },
  grade: { color: 'white', fontSize: 18, fontWeight: '800' },
  scoreRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  scoreLabel: { color: '#ede9fe', width: 82, fontSize: 12, textTransform: 'capitalize' },
  scoreTrack: { flex: 1, height: 7, borderRadius: 8, overflow: 'hidden', backgroundColor: '#ffffff22' },
  scoreFill: { height: '100%', borderRadius: 8 },
  scoreNumber: { color: 'white', width: 26, textAlign: 'right', fontWeight: '800' },
  panel: { padding: 16, borderRadius: 18, backgroundColor: 'white', borderWidth: 1, borderColor: '#e7e0f0' },
  panelTitle: { fontSize: 18, color: '#201633', fontWeight: '900', marginBottom: 12 },
  panelBody: { gap: 9 },
  panelText: { color: '#342846', lineHeight: 20 },
  subcard: { padding: 12, borderRadius: 12, backgroundColor: '#f7f5ff', gap: 5 },
  subcardTitle: { color: '#201633', fontWeight: '800' },
  impact: { color: '#6d28d9', fontWeight: '700', fontSize: 12, lineHeight: 18 },
  benchmarkGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  benchmark: { width: '48%', padding: 11, borderRadius: 12, backgroundColor: '#f7f5ff' },
  benchmarkValue: { color: '#201633', fontWeight: '900', fontSize: 20, marginVertical: 3 },
  positive: { color: '#047857' },
  negative: { color: '#b91c1c' },
  riskText: { color: '#92400e', lineHeight: 20 },
});
