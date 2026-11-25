import type { MediaMimeType, SocialPlatform } from "../../../shared/api";

export type {
  AccountContext,
  AccountInsightsData,
  AIProcessingConsent,
  AuthIntent,
  AudienceComment,
  AudienceComments,
  CaptionInput,
  CaptionResult,
  ComparisonBasis,
  ConnectionStatus,
  Highlight,
  ImageMimeType,
  InstagramConnection,
  InstagramMedia,
  InsightSnapshot,
  MediaMimeType,
  MetricKey,
  MetricValue,
  NotComparableReason,
  PerformanceMetrics,
  PerformancePost,
  PostAnalysisView,
  PublicationResult,
  RangeRow,
  Session,
  Snapshot,
  SocialPlatform,
  SummaryStatus,
  TrackedPost,
  TrackedPostListResponse,
} from "../../../shared/api";

export type Draft = {
  information: string;
  goal: string;
  otherGoal: string;
  platform: SocialPlatform;
  platforms: SocialPlatform[];
  hashtagCount: number;
  useAccountContext: boolean;
  caption: string;
  hashtags: string;
  imageUri?: string;
  imageData?: string;
  imageMimeType?: MediaMimeType;
  mediaKind?: "image" | "video";
  mediaDurationSeconds?: number;
  hasResults: boolean;
};

export type AppScreen = "home" | "create" | "analyze" | "insights" | "settings";
