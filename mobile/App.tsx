import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import * as WebBrowser from "expo-web-browser";
import { SafeAreaProvider, useSafeAreaInsets } from "react-native-safe-area-context";
import { Button } from "./src/components/ui";
import { HomeScreen } from "./src/screens/HomeScreen";
import { CreateScreen } from "./src/screens/CreateScreen";
import { InsightsScreen } from "./src/screens/InsightsScreen";
import { SettingsScreen } from "./src/screens/SettingsScreen";
import { TrackingReportScreen } from "./src/screens/TrackingReportScreen";
import { getSession, logout, requestLoginCode, verifyLoginCode, Session } from "./src/services/auth";
import { connectInstagram, getConnection, getTrackedPost } from "./src/services/api";
import { legalUrl } from "./src/config/environment";
import { AppScreen, Draft, InstagramConnection, TrackedPost } from "./src/types";
import { colors } from "./src/theme/colors";

const emptyDraft: Draft = {
  information: "",
  goal: "Grow engagement",
  otherGoal: "",
  platform: "Instagram",
  platforms: ["Instagram"],
  hashtagCount: 5,
  useAccountContext: true,
  caption: "",
  hashtags: "",
  hasResults: false,
};
const nav: { key: AppScreen; label: string; icon: string }[] = [
  { key: "home", label: "Home", icon: "⌂" },
  { key: "create", label: "Create", icon: "+" },
  { key: "analyze", label: "Analyze", icon: "◎" },
  { key: "insights", label: "Insights", icon: "↗" },
  { key: "settings", label: "Settings", icon: "⚙" },
];
export default function App() {
  return (
    <SafeAreaProvider>
      <AppContent />
    </SafeAreaProvider>
  );
}
function AppContent() {
  const insets = useSafeAreaInsets();
  const [session, setSession] = useState<Session | null>(null);
  const [restoring, setRestoring] = useState(true);
  const [screen, setScreen] = useState<AppScreen>("home");
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [selected, setSelected] = useState<TrackedPost | null>(null);
  const [connection, setConnection] = useState<InstagramConnection | null>(null);
  useEffect(() => {
    getSession()
      .then(setSession)
      .finally(() => setRestoring(false));
  }, []);
  useEffect(() => {
    if (session)
      getConnection(session.accessToken)
        .then(setConnection)
        .catch(() => setConnection(null));
  }, [session]);
  if (restoring)
    return (
      <View style={[styles.safe, styles.center]}>
        <ActivityIndicator color={colors.sky} />
      </View>
    );
  if (!session) return <Login onLogin={setSession} />;
  const openPost = (post: TrackedPost) => {
    setSelected(post);
    setScreen("analyze");
  };
  const openTrackedId = async (id: string) => {
    try {
      setSelected(await getTrackedPost(session.accessToken, id));
      setScreen("analyze");
    } catch (reason) {
      Alert.alert("Analyze", reason instanceof Error ? reason.message : "Could not load this post.");
    }
  };
  const connect = async () => {
    try {
      await connectInstagram(session.accessToken);
      setConnection(await getConnection(session.accessToken));
    } catch (reason) {
      Alert.alert("Instagram connection", reason instanceof Error ? reason.message : "Could not connect Instagram.");
    }
  };
  return (
    <View style={[styles.safe, { paddingTop: insets.top }]}>
      <StatusBar style="dark" />
      <KeyboardAvoidingView style={styles.appContent} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <View style={styles.body}>
          {screen === "home" && <HomeScreen accessToken={session.accessToken} onOpen={openPost} />}
          {screen === "create" && (
            <CreateScreen draft={draft} setDraft={setDraft} connection={connection} accessToken={session.accessToken} />
          )}
          {screen === "analyze" && (
            <TrackingReportScreen
              accessToken={session.accessToken}
              initial={selected}
              onBack={selected ? () => setSelected(null) : undefined}
            />
          )}
          {screen === "insights" && (
            <InsightsScreen
              accessToken={session.accessToken}
              onOpen={(id) => void openTrackedId(id)}
              onConnect={connect}
            />
          )}
          {screen === "settings" && (
            <SettingsScreen
              email={session.user.email}
              accessToken={session.accessToken}
              onLogout={async () => {
                await logout(session);
                setSession(null);
              }}
              onAccountDeleted={() => setSession(null)}
            />
          )}
        </View>
        <View style={[styles.nav, { paddingBottom: insets.bottom }]}>
          {nav.map((item) => (
            <Pressable
              key={item.key}
              onPress={() => {
                if (item.key === "analyze") setSelected(null);
                setScreen(item.key);
              }}
              style={styles.navItem}
            >
              <Text style={[styles.navIcon, screen === item.key && styles.navActive]}>{item.icon}</Text>
              <Text style={[styles.navText, screen === item.key && styles.navActive]}>{item.label}</Text>
            </Pressable>
          ))}
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}
function Login({ onLogin }: { onLogin: (session: Session) => void }) {
  const insets = useSafeAreaInsets();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const openLegal = (path: "/privacy" | "/terms") => {
    void WebBrowser.openBrowserAsync(legalUrl(path)).catch(() =>
      Alert.alert("Could not open this page", "Try again later."),
    );
  };
  const submit = async () => {
    if (!email.includes("@")) return Alert.alert("Enter a valid email");
    setBusy(true);
    try {
      if (!sent) {
        const result = await requestLoginCode(email.trim());
        setSent(true);
        if (result.developmentCode) setCode(result.developmentCode);
      } else onLogin(await verifyLoginCode(email.trim(), code.trim()));
    } catch (reason) {
      Alert.alert("Sign in failed", reason instanceof Error ? reason.message : "Try again.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      style={[styles.login, { paddingTop: insets.top + 28, paddingBottom: insets.bottom + 28 }]}
    >
      <StatusBar style="light" />
      <Text style={styles.logo}>PB</Text>
      <Text style={styles.welcome}>Bridge every post to better results.</Text>
      <TextInput
        accessibilityLabel="Email"
        editable={!sent}
        style={styles.input}
        autoCapitalize="none"
        keyboardType="email-address"
        placeholder="you@example.com"
        value={email}
        onChangeText={setEmail}
      />
      {sent && (
        <TextInput
          accessibilityLabel="Sign-in code"
          style={styles.input}
          keyboardType="number-pad"
          maxLength={6}
          placeholder="6-digit code"
          value={code}
          onChangeText={setCode}
        />
      )}
      <View style={styles.legalLinks}>
        <Pressable accessibilityRole="link" onPress={() => openLegal("/privacy")}>
          <Text style={styles.legalLink}>Privacy</Text>
        </Pressable>
        <Text style={styles.legalSeparator}>·</Text>
        <Pressable accessibilityRole="link" onPress={() => openLegal("/terms")}>
          <Text style={styles.legalLink}>Terms</Text>
        </Pressable>
      </View>
      <Button
        label={busy ? "Please wait…" : sent ? "Verify and sign in" : "Email me a code"}
        onPress={submit}
        disabled={busy}
      />
      {sent && (
        <Button
          label="Use a different email"
          onPress={() => {
            setSent(false);
            setCode("");
          }}
          secondary
        />
      )}
    </KeyboardAvoidingView>
  );
}
const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.canvas },
  center: { alignItems: "center", justifyContent: "center" },
  appContent: { flex: 1 },
  body: { flex: 1 },
  nav: {
    minHeight: 70,
    flexDirection: "row",
    backgroundColor: colors.sidebar,
    borderTopWidth: 1,
    borderTopColor: colors.line,
  },
  navItem: { flex: 1, minHeight: 70, gap: 2, alignItems: "center", justifyContent: "center" },
  navIcon: { minHeight: 22, fontSize: 21, lineHeight: 23, color: colors.muted, fontWeight: "700" },
  navText: { fontSize: 11, color: colors.muted, fontWeight: "700" },
  navActive: { color: colors.primary },
  login: { flex: 1, backgroundColor: colors.ink, paddingHorizontal: 28, justifyContent: "center", gap: 18 },
  logo: {
    color: colors.white,
    fontSize: 22,
    fontWeight: "900",
    backgroundColor: colors.primary,
    width: 60,
    height: 60,
    textAlign: "center",
    textAlignVertical: "center",
    borderRadius: 18,
  },
  welcome: { color: colors.white, fontSize: 36, fontWeight: "900" },
  input: {
    minHeight: 50,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.field,
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: colors.ink,
  },
  legalLinks: { flexDirection: "row", justifyContent: "center", gap: 9 },
  legalLink: { color: colors.white85, fontSize: 13, fontWeight: "800", textDecorationLine: "underline" },
  legalSeparator: { color: colors.white85, fontSize: 13 },
});
