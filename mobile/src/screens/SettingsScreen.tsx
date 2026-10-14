import { useCallback, useEffect, useState } from 'react';
import { Alert, ScrollView, StyleSheet, Text, View } from 'react-native';
import { InstagramAccountCard } from '../components/InstagramAccountCard';
import { Button } from '../components/ui';
import { connectInstagram, disconnectInstagram, getConnection } from '../services/api';
import { InstagramConnection } from '../types';

export function SettingsScreen({ email, onLogout }: { email: string; onLogout: () => Promise<void> }) {
  const [connection, setConnection] = useState<InstagramConnection>({ connected: false, configured: false, status: 'not_connected' }); const [error, setError] = useState('');
  const load = useCallback(async () => { try { setConnection(await getConnection(email)); setError(''); } catch (e) { setError(e instanceof Error ? e.message : 'Could not load connection.'); } }, [email]);
  // The state updates in load happen as part of the asynchronous API request.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load(); }, [load]);
  const connect = async () => { try { await connectInstagram(email); await load(); } catch (e) { setError(e instanceof Error ? e.message : 'Could not connect Instagram.'); } };
  const confirmDisconnect = () => Alert.alert('Disconnect Instagram?', 'Instagram Insights will stop updating. Your CreatorMind account and historical snapshots will be kept.', [{ text: 'Cancel', style: 'cancel' }, { text: 'Disconnect', style: 'destructive', onPress: async () => { await disconnectInstagram(email); await load(); } }]);
  return <ScrollView contentContainerStyle={styles.content}><Text style={styles.title}>Settings</Text><Text style={styles.sectionTitle}>Account</Text><View style={styles.card}><Text style={styles.email}>{email}</Text><Button label="Log out" onPress={onLogout} secondary /></View><Text style={styles.sectionTitle}>Connected accounts</Text>{error ? <Text style={styles.error}>{error}</Text> : null}<InstagramAccountCard connection={connection} onConnect={connect} onRefresh={load} onDisconnect={confirmDisconnect} /></ScrollView>;
}
const styles = StyleSheet.create({ content: { padding: 20, paddingBottom: 32, gap: 14 }, title: { fontSize: 30, lineHeight: 36, fontWeight: '800', color: '#201633' }, sectionTitle: { fontWeight: '800', fontSize: 18, color: '#201633' }, card: { padding: 18, borderRadius: 18, backgroundColor: 'white', gap: 14, borderWidth: 1, borderColor: '#ebe6f2' }, email: { fontWeight: '700', color: '#201633' }, error: { color: '#b91c1c' } });
