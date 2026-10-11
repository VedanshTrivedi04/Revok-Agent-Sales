export interface EnvironmentLabel {
  text: string;
  /** Production gets the strongest treatment so nobody mistakes it for staging. */
  isProduction: boolean;
}

/** Maps the API's APP_ENV (from `GET /admin/me`) to the label shown in the Internal badge area. */
export function environmentLabel(environment: string | undefined): EnvironmentLabel {
  switch ((environment ?? "").toLowerCase()) {
    case "prod":
    case "production":
      return { text: "PROD", isProduction: true };
    case "staging":
      return { text: "STAGING", isProduction: false };
    case "local":
    case "test":
      return { text: "LOCAL", isProduction: false };
    case "":
      return { text: "—", isProduction: false };
    default:
      return { text: environment!.toUpperCase(), isProduction: false };
  }
}
