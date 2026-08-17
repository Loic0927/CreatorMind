import { useEffect, useState } from 'react';
import { ActivityIndicator, Alert, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider, useSafeAreaInsets } from 'react-native-safe-area-context';
import { InstagramPostPreview } from './src/components/InstagramPostPreview';
import { Button } from './src/components/ui';
import { HomeScreen } from './src/screens/HomeScreen';
import { CreateScreen } from './src/screens/CreateScreen';
import { InsightsScreen } from './src/screens/InsightsScreen';
import { SettingsScreen } from './src/screens/SettingsScreen';
import { TrackingReportScreen } from './src/screens/TrackingReportScreen';
import { clearSession, getSession, saveDemoSession, Session } from './src/services/auth';
import { connectInstagram, getConnection } from './src/services/api';
import { AppScreen, Draft, InstagramConnection, TrackedPost } from './src/types';

const emptyDraft: Draft = { information: '', goal: '', otherGoal: '', caption: '', hashtags: '', hasResults: false };

export default function App() { return <SafeAreaProvider><AppContent /></SafeAreaProvider>; }

function AppContent() {
  const insets = useSafeAreaInsets(); const [session, setSession] = useState<Session | null>(null); const [restoring, setRestoring] = useState(true); const [screen, setScreen] = useState<AppScreen>('home'); const [draft, setDraft] = useState<Draft>(emptyDraft); const [selected, setSelected] = useState<TrackedPost | null>(null); const [connection, setConnection] = useState<InstagramConnection | null>(null);
  useEffect(() => { getSession().then(setSession).finally(() => setRestoring(false)); }, []);
  useEffect(() => { if (session) getConnection(session.email).then(setConnection).catch(() => setConnection(null)); }, [session]);
  if (restoring) return <View style={[styles.safe, styles.center]}><ActivityIndicator color="#7c3aed" /></View>;
  if (!session) return <Login onLogin={async (email) => { const value = await saveDemoSession(email); setSession(value); }} />;
  const openTracking = (post: TrackedPost) => { setSelected(post); setScreen('tracking'); };
  const connect = async () => { try { await connectInstagram(session.email); setConnection(await getConnection(session.email)); } catch (e) { Alert.alert('Instagram connection', e instanceof Error ? e.message : 'Could not connect Instagram.'); } };
  return <View style={styles.safe}><StatusBar style="dark" /><View style={[styles.header, { paddingTop: insets.top }]}><View style={styles.headerContent}><Text style={styles.brand}>CreatorMind</Text></View></View><KeyboardAvoidingView style={styles.appContent} behavior={Platform.OS === 'ios' ? 'padding' : undefined}><View style={styles.body}>{screen === 'home' && <HomeScreen userId={session.email} onOpen={openTracking} />}{screen === 'create' && <CreateScreen draft={draft} setDraft={setDraft} connection={connection} onPreview={() => setScreen('preview')} />}{screen === 'preview' && draft.imageUri && <ScrollView contentContainerStyle={styles.preview}><Text style={styles.title}>Publish preview</Text><InstagramPostPreview imageUri={draft.imageUri} caption={draft.caption} hashtags={draft.hashtags} connection={connection} /><Button label="Back to edit" onPress={() => setScreen('create')} secondary /></ScrollView>}{screen === 'insights' && <InsightsScreen userId={session.email} onOpen={openTracking} onConnect={connect} />}{screen === 'settings' && <SettingsScreen email={session.email} onLogout={async () => { await clearSession(); setSession(null); }} />}{screen === 'tracking' && selected && <TrackingReportScreen userId={session.email} initial={selected} onBack={() => setScreen('home')} />}</View><View style={[styles.nav, { paddingBottom: insets.bottom }]}>{(['home', 'create', 'insights', 'settings'] as const).map((item) => <Pressable key={item} onPress={() => setScreen(item)} style={styles.navItem}><Text style={[styles.navText, (screen === item || (screen === 'tracking' && item === 'home')) && styles.navActive]}>{item[0].toUpperCase() + item.slice(1)}</Text></Pressable>)}</View></KeyboardAvoidingView></View>;
}

function Login({ onLogin }: { onLogin: (email: string) => Promise<void> }) {
  const insets = useSafeAreaInsets(); const [email, setEmail] = useState(''); const submit = async () => { if (!email.includes('@')) return Alert.alert('Enter a valid email'); await onLogin(email.trim()); };
  return <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={[styles.login, { paddingTop: insets.top + 28, paddingBottom: insets.bottom + 28 }]}><StatusBar style="light" /><Text style={styles.logo}>CM</Text><Text style={styles.welcome}>Create with clarity.</Text><TextInput accessibilityLabel="Email" style={styles.input} autoCapitalize="none" keyboardType="email-address" placeholder="you@example.com" value={email} onChangeText={setEmail} /><Button label="Continue" onPress={submit} /></KeyboardAvoidingView>;
}

const styles = StyleSheet.create({ safe: { flex: 1, backgroundColor: '#f7f5ff' }, center: { alignItems: 'center', justifyContent: 'center' }, appContent: { flex: 1 }, body: { flex: 1 }, header: { backgroundColor: '#f7f5ff', borderBottomWidth: 1, borderBottomColor: '#e7e0f7' }, headerContent: { minHeight: 48, paddingHorizontal: 20, justifyContent: 'center' }, brand: { fontWeight: '800', fontSize: 20, color: '#201633' }, nav: { minHeight: 56, flexDirection: 'row', paddingHorizontal: 20, backgroundColor: 'white', borderTopWidth: 1, borderTopColor: '#e7e0f0' }, navItem: { flex: 1, minHeight: 56, alignItems: 'center', justifyContent: 'center' }, navText: { fontSize: 12, color: '#80778b', fontWeight: '700' }, navActive: { color: '#7c3aed' }, login: { flex: 1, backgroundColor: '#24163b', paddingHorizontal: 28, justifyContent: 'center', gap: 18 }, logo: { color: 'white', fontSize: 22, fontWeight: '900', backgroundColor: '#7c3aed', width: 60, height: 60, textAlign: 'center', textAlignVertical: 'center', borderRadius: 18 }, welcome: { color: 'white', fontSize: 36, fontWeight: '900' }, input: { minHeight: 50, borderWidth: 1, borderColor: '#ddd5e8', backgroundColor: 'white', borderRadius: 14, paddingHorizontal: 14, paddingVertical: 12, color: '#201633' }, preview: { padding: 20, paddingBottom: 32, gap: 14 }, title: { fontSize: 30, lineHeight: 36, fontWeight: '800', color: '#201633' } });
