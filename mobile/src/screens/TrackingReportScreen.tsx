import { useCallback, useEffect, useState } from 'react';
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
          <Text style={styles.historySummary}>{analysis.output_payload.summary}</Text>
          <Text style={styles.label}>{new Date(analysis.created_at).toLocaleString()} · {analysis.model_name}</Text>
          <Text style={styles.snapshotId}>Snapshot {analysis.source_snapshot_id.slice(0, 8)}</Text>
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
  return (
    <View style={styles.analysis}>
      <Text style={styles.eyebrow}>MODEL INTERPRETATION</Text>
      <Text style={styles.analysisSummary}>{output.summary}</Text>
      <Text style={styles.analysisTitle}>Observed provider data</Text>
      <View style={styles.analysisMetrics}>
        {Object.entries(analysis.observed_metrics).map(([name, value]) => (
          <View key={name} style={styles.analysisMetric}>
            <Text style={styles.analysisValue}>{value ?? '—'}</Text>
            <Text style={styles.analysisLabel}>{name.replaceAll('_', ' ')}</Text>
            {analysis.metric_deltas[name] != null && <Text style={styles.delta}>Δ {formatDelta(analysis.metric_deltas[name])}</Text>}
          </View>
        ))}
      </View>
      <AnalysisList title="What performed well" items={output.strengths} />
      <AnalysisList title="Needs attention" items={output.concerns} />
      <AnalysisList title="Next actions" items={output.recommendations} />
      <AnalysisList title="Unavailable inputs" items={output.missing_inputs} />
      <Text style={styles.source}>Snapshot {analysis.source_snapshot_id.slice(0, 8)} · {analysis.model_name}</Text>
    </View>
  );
}

function AnalysisList({ title, items }: { title: string; items: string[] }) {
  return (
    <View style={styles.analysisList}>
      <Text style={styles.analysisTitle}>{title}</Text>
      {items.length ? items.map((item) => <Text key={item} style={styles.analysisItem}>• {item}</Text>) : <Text style={styles.analysisMuted}>No item reported.</Text>}
    </View>
  );
}

function formatDelta(value: number | null) {
  if (value == null) return '—';
  return value > 0 ? `+${value}` : String(value);
}

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
});
