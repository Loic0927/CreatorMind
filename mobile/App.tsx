import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Image,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import * as WebBrowser from "expo-web-browser";
import { SafeAreaProvider, useSafeAreaInsets } from "react-native-safe-area-context";
import { HomeScreen } from "./src/screens/HomeScreen";
import { CreateScreen } from "./src/screens/CreateScreen";
import { InsightsScreen } from "./src/screens/InsightsScreen";
import { SettingsScreen } from "./src/screens/SettingsScreen";
import { TrackingReportScreen } from "./src/screens/TrackingReportScreen";
import { AuthIntent, getSession, logout, requestLoginCode, verifyLoginCode, Session } from "./src/services/auth";
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
export function Login({ onLogin }: { onLogin: (session: Session) => void }) {
  const insets = useSafeAreaInsets();
  const [intent, setIntent] = useState<AuthIntent>("sign_in");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [registrationVisible, setRegistrationVisible] = useState(false);
  const [legalAccepted, setLegalAccepted] = useState(false);
  const [aiAccepted, setAiAccepted] = useState(false);

  const openUrl = (url: string) => {
    void WebBrowser.openBrowserAsync(url).catch(() => Alert.alert("Could not open this page", "Try again later."));
  };
  const openLegal = (path: "/privacy" | "/terms") => openUrl(legalUrl(path));
  const changeIntent = (next: AuthIntent) => {
    setIntent(next);
    setSent(false);
    setCode("");
    setRegistrationVisible(false);
    setLegalAccepted(false);
    setAiAccepted(false);
  };
  const submit = async () => {
    if (!email.includes("@")) return Alert.alert("Enter a valid email");
    if (sent && code.trim().length !== 6) return Alert.alert("Enter the six-digit verification code");
    if (sent && intent === "sign_up") {
      setRegistrationVisible(true);
      return;
    }
    setBusy(true);
    try {
      if (!sent) {
        const result = await requestLoginCode(email.trim(), intent);
        setSent(true);
        if (result.developmentCode) setCode(result.developmentCode);
      } else {
        onLogin(await verifyLoginCode(email.trim(), code.trim(), { intent: "sign_in" }));
      }
    } catch (reason) {
      Alert.alert(
        intent === "sign_up" ? "Create account failed" : "Sign in failed",
        reason instanceof Error ? reason.message : "Try again.",
      );
    } finally {
      setBusy(false);
    }
  };
  const completeRegistration = async () => {
    if (!legalAccepted || !aiAccepted) return;
    setBusy(true);
    try {
      onLogin(
        await verifyLoginCode(email.trim(), code.trim(), {
          intent: "sign_up",
          privacyTermsAccepted: true,
          aiProcessingConsent: true,
        }),
      );
    } catch (reason) {
      Alert.alert("Create account failed", reason instanceof Error ? reason.message : "Try again.");
    } finally {
      setBusy(false);
    }
  };

  const title = intent === "sign_up" ? "Create account" : "Sign in";
  return (
    <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.loginPage}>
      <StatusBar style="dark" />
      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={[styles.loginScroll, { paddingTop: insets.top + 24, paddingBottom: insets.bottom + 32 }]}
      >
        <View style={styles.loginCard}>
          <Image
            source={require("./assets/loginpage.png")}
            resizeMode="contain"
            accessibilityLabel="PostBridge fox holding a glowing idea bulb"
            style={styles.loginMascot}
          />
          <Text accessibilityRole="header" style={styles.loginTitle}>
            {title}
          </Text>
          <View style={styles.loginDividerRow}>
            <View style={styles.loginDivider} />
            <Text style={styles.loginDividerText}>secure email verification</Text>
            <View style={styles.loginDivider} />
          </View>
          <View style={styles.loginField}>
            <Text style={styles.loginLabel}>Email</Text>
            <TextInput
              accessibilityLabel="Email"
              editable={!sent && !busy}
              style={styles.loginInput}
              autoCapitalize="none"
              autoComplete="email"
              keyboardType="email-address"
              placeholder="name@company.com"
              placeholderTextColor={colors.muted}
              value={email}
              onChangeText={setEmail}
            />
          </View>
          {sent ? (
            <View style={styles.loginField}>
              <Text style={styles.loginLabel}>Verification code</Text>
              <TextInput
                accessibilityLabel="Verification code"
                editable={!busy}
                style={styles.loginInput}
                autoComplete="one-time-code"
                keyboardType="number-pad"
                maxLength={6}
                placeholder="6-digit code"
                placeholderTextColor={colors.muted}
                value={code}
                onChangeText={(value) => setCode(value.replace(/\D/g, ""))}
              />
            </View>
          ) : null}
          <Pressable
            accessibilityRole="button"
            disabled={busy || !email.trim() || (sent && code.length !== 6)}
            onPress={() => void submit()}
            style={({ pressed }) => [
              styles.loginPrimaryButton,
              pressed && styles.loginButtonPressed,
              (busy || !email.trim() || (sent && code.length !== 6)) && styles.loginButtonDisabled,
            ]}
          >
            <Text style={styles.loginPrimaryButtonText}>
              {busy
                ? "Please wait…"
                : sent
                  ? intent === "sign_up"
                    ? "Review and create account"
                    : "Verify and sign in"
                  : "Email me a code"}
            </Text>
          </Pressable>
          {sent ? (
            <Pressable
              accessibilityRole="button"
              disabled={busy}
              onPress={() => {
                setSent(false);
                setCode("");
              }}
            >
              <Text style={styles.changeEmail}>Use a different email</Text>
            </Pressable>
          ) : null}
          <View style={styles.loginSwitchRow}>
            <Text style={styles.loginSwitchText}>
              {intent === "sign_up" ? "Already have an account?" : "Don’t have an account?"}
            </Text>
            <Pressable
              accessibilityRole="button"
              onPress={() => changeIntent(intent === "sign_up" ? "sign_in" : "sign_up")}
            >
              <Text style={styles.loginSwitchLink}>{intent === "sign_up" ? "Sign in" : "Create account"}</Text>
            </Pressable>
          </View>
        </View>
      </ScrollView>

      <Modal
        visible={registrationVisible}
        transparent
        animationType="fade"
        statusBarTranslucent
        onRequestClose={busy ? undefined : () => setRegistrationVisible(false)}
      >
        <View style={styles.registrationBackdrop}>
          <View accessibilityViewIsModal style={styles.registrationSheet}>
            <ScrollView contentContainerStyle={styles.registrationContent}>
              <Text style={styles.registrationEyebrow}>BEFORE WE CREATE YOUR ACCOUNT</Text>
              <Text accessibilityRole="header" style={styles.registrationTitle}>
                Privacy, Terms & AI processing
              </Text>
              <Text style={styles.registrationBody}>
                Review these notices here. Your account is not created until you confirm both choices below.
              </Text>
              <View style={styles.registrationNotice}>
                <Text style={styles.registrationNoticeTitle}>Privacy</Text>
                <Text style={styles.registrationBody}>
                  PostBridge stores your account details and the Instagram data you connect for publishing, tracking,
                  and analysis. You can request account deletion from Settings.
                </Text>
                <Pressable accessibilityRole="link" onPress={() => openLegal("/privacy")}>
                  <Text style={styles.registrationLink}>Read the full Privacy Policy</Text>
                </Pressable>
              </View>
              <View style={styles.registrationNotice}>
                <Text style={styles.registrationNoticeTitle}>Terms</Text>
                <Text style={styles.registrationBody}>
                  Use PostBridge lawfully, protect your access, and review AI-generated content before using or
                  publishing it. Connected services have their own terms.
                </Text>
                <Pressable accessibilityRole="link" onPress={() => openLegal("/terms")}>
                  <Text style={styles.registrationLink}>Read the full Terms</Text>
                </Pressable>
              </View>
              <View style={styles.registrationNotice}>
                <Text style={styles.registrationNoticeTitle}>AI processing</Text>
                <Text style={styles.registrationBody}>
                  For captions, summaries, comment summaries, and suggestions, PostBridge may send relevant post media,
                  captions, audience comments, and performance facts to Google Gemini.
                </Text>
              </View>
              <ConsentRow
                checked={legalAccepted}
                label="I have read and agree to the Privacy Policy and Terms."
                onPress={() => setLegalAccepted((value) => !value)}
              />
              <ConsentRow
                checked={aiAccepted}
                label="I agree to the AI processing described above, including processing by Google Gemini."
                onPress={() => setAiAccepted((value) => !value)}
              />
              <View style={styles.registrationActions}>
                <Pressable
                  accessibilityRole="button"
                  disabled={busy}
                  onPress={() => setRegistrationVisible(false)}
                  style={[styles.registrationButton, styles.registrationCancel, busy && styles.loginButtonDisabled]}
                >
                  <Text style={styles.registrationCancelText}>Cancel</Text>
                </Pressable>
                <Pressable
                  accessibilityRole="button"
                  disabled={busy || !legalAccepted || !aiAccepted}
                  onPress={() => void completeRegistration()}
                  style={[
                    styles.registrationButton,
                    styles.registrationConfirm,
                    (busy || !legalAccepted || !aiAccepted) && styles.loginButtonDisabled,
                  ]}
                >
                  <Text style={styles.registrationConfirmText}>{busy ? "Creating…" : "Agree and create account"}</Text>
                </Pressable>
              </View>
            </ScrollView>
          </View>
        </View>
      </Modal>
    </KeyboardAvoidingView>
  );
}

function ConsentRow({ checked, label, onPress }: { checked: boolean; label: string; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityState={{ checked }}
      onPress={onPress}
      style={styles.consentRow}
    >
      <View style={[styles.consentBox, checked && styles.consentBoxChecked]}>
        {checked ? <Text style={styles.consentCheck}>✓</Text> : null}
      </View>
      <Text style={styles.consentLabel}>{label}</Text>
    </Pressable>
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
  loginPage: { flex: 1, backgroundColor: "#EEF3FF" },
  loginScroll: { flexGrow: 1, paddingHorizontal: 20 },
  loginCard: {
    width: "100%",
    maxWidth: 540,
    alignSelf: "center",
    alignItems: "stretch",
    paddingHorizontal: 24,
    paddingVertical: 30,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.9)",
    backgroundColor: colors.surface,
    shadowColor: colors.ink,
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.1,
    shadowRadius: 22,
    elevation: 5,
  },
  loginMascot: { width: 180, height: 180, alignSelf: "center" },
  loginTitle: { color: colors.ink, fontSize: 38, lineHeight: 44, fontWeight: "900", textAlign: "center" },
  loginDividerRow: { flexDirection: "row", alignItems: "center", gap: 10, marginVertical: 24 },
  loginDivider: { flex: 1, height: 1, backgroundColor: colors.line },
  loginDividerText: { color: colors.muted, fontSize: 12, fontWeight: "700" },
  loginField: { marginBottom: 18 },
  loginLabel: { marginBottom: 8, color: colors.ink, fontSize: 14, fontWeight: "800" },
  loginInput: {
    width: "100%",
    minHeight: 58,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: "#EAF2FF",
    borderRadius: 16,
    paddingHorizontal: 18,
    paddingVertical: 14,
    color: colors.ink,
    fontSize: 16,
  },
  loginPrimaryButton: {
    minHeight: 56,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 16,
    paddingHorizontal: 18,
    backgroundColor: "#655CFF",
    shadowColor: "#5669FF",
    shadowOffset: { width: 0, height: 9 },
    shadowOpacity: 0.25,
    shadowRadius: 16,
    elevation: 4,
  },
  loginPrimaryButtonText: { color: colors.white, fontSize: 16, fontWeight: "900", textAlign: "center" },
  loginButtonPressed: { opacity: 0.88 },
  loginButtonDisabled: { opacity: 0.5 },
  changeEmail: { marginTop: 20, color: colors.primary, fontSize: 14, fontWeight: "800" },
  loginSwitchRow: {
    marginTop: 28,
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "center",
    gap: 5,
  },
  loginSwitchText: { color: colors.muted, fontSize: 14 },
  loginSwitchLink: { color: colors.primary, fontSize: 14, fontWeight: "800" },
  registrationBackdrop: {
    flex: 1,
    justifyContent: "center",
    padding: 18,
    backgroundColor: colors.overlay,
  },
  registrationSheet: {
    width: "100%",
    maxWidth: 640,
    maxHeight: "92%",
    alignSelf: "center",
    overflow: "hidden",
    borderRadius: 24,
    backgroundColor: colors.surface,
  },
  registrationContent: { padding: 22, gap: 14 },
  registrationEyebrow: { color: colors.primaryHover, fontSize: 10, fontWeight: "900", letterSpacing: 1 },
  registrationTitle: { color: colors.ink, fontSize: 25, lineHeight: 31, fontWeight: "900" },
  registrationBody: { color: colors.inkSoft, fontSize: 13, lineHeight: 20 },
  registrationNotice: { gap: 8, borderRadius: 16, backgroundColor: colors.subtle, padding: 14 },
  registrationNoticeTitle: { color: colors.ink, fontSize: 15, fontWeight: "900" },
  registrationLink: { color: colors.primary, fontSize: 13, fontWeight: "800", textDecorationLine: "underline" },
  consentRow: {
    minWidth: 0,
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 11,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 14,
    padding: 14,
  },
  consentBox: {
    width: 22,
    height: 22,
    flexShrink: 0,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 2,
    borderColor: colors.checkboxBorder,
    borderRadius: 6,
    backgroundColor: colors.surface,
  },
  consentBoxChecked: { borderColor: colors.primary, backgroundColor: colors.primary },
  consentCheck: { color: colors.white, fontSize: 14, lineHeight: 17, fontWeight: "900" },
  consentLabel: { minWidth: 0, flex: 1, color: colors.ink, fontSize: 13, lineHeight: 19, fontWeight: "700" },
  registrationActions: { flexDirection: "column-reverse", gap: 10, marginTop: 4 },
  registrationButton: { minHeight: 50, alignItems: "center", justifyContent: "center", borderRadius: 14, padding: 12 },
  registrationCancel: { borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface },
  registrationConfirm: { backgroundColor: "#655CFF" },
  registrationCancelText: { color: colors.inkSoft, fontWeight: "800" },
  registrationConfirmText: { color: colors.white, fontWeight: "900", textAlign: "center" },
});
