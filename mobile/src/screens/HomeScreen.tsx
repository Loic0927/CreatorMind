import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Image,
  Modal,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { connectInstagram, getConnection, getInstagramMedia, getTrackedPosts, trackPost } from "../services/api";
import { InstagramConnection, InstagramMedia, TrackedPost } from "../types";
import { TrackedPostCard } from "../components/TrackedPostCard";
import { Button } from "../components/ui";
import { colors } from "../theme/colors";

export function HomeScreen({ accessToken, onOpen }: { accessToken: string; onOpen: (post: TrackedPost) => void }) {
  const insets = useSafeAreaInsets();
  const [connection, setConnection] = useState<InstagramConnection | null>(null);
  const [posts, setPosts] = useState<TrackedPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selector, setSelector] = useState(false);
  const [media, setMedia] = useState<InstagramMedia[]>([]);
  const [mediaLoading, setMediaLoading] = useState(false);
  const load = useCallback(
    () =>
      Promise.all([getConnection(accessToken), getTrackedPosts(accessToken)])
        .then(([nextConnection, tracked]) => {
          setError("");
          setConnection(nextConnection);
          setPosts(tracked.items);
        })
        .catch((e) => setError(e instanceof Error ? e.message : "Could not load tracked posts."))
        .finally(() => setLoading(false)),
    [accessToken],
  );
  useEffect(() => {
    load();
  }, [load]);
  const openSelector = async () => {
    if (!connection?.connected) {
      try {
        await connectInstagram(accessToken);
        await load();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not connect Instagram.");
      }
      return;
    }
    setSelector(true);
    setMediaLoading(true);
    try {
      const result = await getInstagramMedia(accessToken);
      setMedia(result.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load Instagram posts.");
    } finally {
      setMediaLoading(false);
    }
  };
  const trackedIds = new Set(posts.map((post) => post.media.id));
  return (
    <View style={styles.page}>
      <ScrollView
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        contentContainerStyle={styles.content}
      >
        <Text style={styles.title}>Tracked posts</Text>
        {loading ? (
          <ActivityIndicator color={colors.sky} />
        ) : error ? (
          <State message={error} action="Try again" onPress={load} />
        ) : !connection?.connected ? (
          <State message="Connect Instagram to track your posts." action="Connect Instagram" onPress={openSelector} />
        ) : posts.length === 0 ? (
          <State message="No tracked posts yet." action="Add a post" onPress={openSelector} />
        ) : (
          posts.map((post) => <TrackedPostCard key={post.tracking.id} post={post} onPress={() => onOpen(post)} />)
        )}
        <View style={{ height: 72 }} />
      </ScrollView>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Add a tracked post"
        onPress={openSelector}
        style={[styles.fab, { bottom: 16 + Math.min(insets.bottom, 12) }]}
      >
        <Text style={styles.plus}>＋</Text>
      </Pressable>
      <Modal visible={selector} animationType="slide" onRequestClose={() => setSelector(false)}>
        <View style={[styles.modal, { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16 }]}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>Add a post</Text>
            <Pressable onPress={() => setSelector(false)}>
              <Text style={styles.close}>Close</Text>
            </Pressable>
          </View>
          {mediaLoading ? (
            <ActivityIndicator color={colors.sky} />
          ) : media.length === 0 ? (
            <Text style={styles.empty}>No Instagram posts found.</Text>
          ) : (
            <ScrollView contentContainerStyle={styles.mediaGrid}>
              {media.map((item) => {
                const tracked = trackedIds.has(item.id);
                return (
                  <Pressable
                    disabled={tracked}
                    key={item.id}
                    accessibilityLabel={tracked ? "Tracked Instagram post" : "Track Instagram post"}
                    onPress={async () => {
                      await trackPost(accessToken, item.id);
                      setSelector(false);
                      setLoading(true);
                      await load();
                    }}
                    style={styles.mediaCell}
                  >
                    {item.thumbnail_url || item.media_url ? (
                      <Image source={{ uri: item.thumbnail_url || item.media_url }} style={styles.mediaImage} />
                    ) : (
                      <View style={styles.mediaImage} />
                    )}
                    {tracked && (
                      <View style={styles.tracked}>
                        <Text style={styles.trackedText}>Tracked</Text>
                      </View>
                    )}
                  </Pressable>
                );
              })}
            </ScrollView>
          )}
        </View>
      </Modal>
    </View>
  );
}
function State({ message, action, onPress }: { message: string; action: string; onPress: () => void | Promise<void> }) {
  return (
    <View style={styles.state}>
      <Text style={styles.empty}>{message}</Text>
      <Button label={action} onPress={onPress} />
    </View>
  );
}
const styles = StyleSheet.create({
  page: { flex: 1 },
  content: { padding: 20, gap: 14 },
  title: { fontSize: 30, lineHeight: 36, fontWeight: "800", color: colors.ink },
  state: {
    marginTop: 32,
    padding: 22,
    borderRadius: 18,
    backgroundColor: colors.surface,
    gap: 16,
    borderWidth: 1,
    borderColor: colors.line,
  },
  empty: { color: colors.muted, textAlign: "center" },
  fab: {
    position: "absolute",
    right: 20,
    width: 58,
    height: 58,
    borderRadius: 29,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    elevation: 5,
    shadowOpacity: 0.2,
    shadowRadius: 6,
  },
  plus: { color: colors.white, fontSize: 32, lineHeight: 36 },
  modal: { flex: 1, backgroundColor: colors.canvas, paddingHorizontal: 20 },
  modalHeader: { minHeight: 52, flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  modalTitle: { fontSize: 26, fontWeight: "800", color: colors.ink },
  close: { color: colors.primary, fontWeight: "700" },
  mediaGrid: { flexDirection: "row", flexWrap: "wrap", gap: 6, paddingVertical: 12 },
  mediaCell: { width: "32%", aspectRatio: 1 },
  mediaImage: { width: "100%", height: "100%", backgroundColor: colors.selected },
  tracked: {
    ...StyleSheet.absoluteFill,
    backgroundColor: colors.overlayStrong,
    alignItems: "center",
    justifyContent: "center",
  },
  trackedText: { color: colors.white, fontWeight: "800" },
});
