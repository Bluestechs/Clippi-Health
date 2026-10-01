const path = require("node:path");
const fs = require("node:fs");
const { execFileSync } = require("node:child_process");
const plist = require("plist");
const { FusesPlugin } = require("@electron-forge/plugin-fuses");
const { FuseVersion, FuseV1Options } = require("@electron/fuses");

const assets = path.resolve(__dirname, "..", "assets", "icons");
const platformIcon = process.platform === "darwin"
  ? path.join(assets, "clippi-health.icns")
  : process.platform === "win32"
    ? path.join(assets, "clippi-health.ico")
    : path.join(assets, "clippi-health.png");

function macNotarization() {
  if (!process.env.APPLE_API_KEY || !process.env.APPLE_API_KEY_ID || !process.env.APPLE_API_ISSUER) return undefined;
  return {
    tool: "notarytool",
    appleApiKey: process.env.APPLE_API_KEY,
    appleApiKeyId: process.env.APPLE_API_KEY_ID,
    appleApiIssuer: process.env.APPLE_API_ISSUER,
  };
}

function azureWindowsSigning() {
  if (!process.env.AZURE_CODE_SIGNING_DLIB || !process.env.AZURE_METADATA_JSON) return undefined;
  return {
    ...(process.env.SIGNTOOL_PATH ? { signToolPath: process.env.SIGNTOOL_PATH } : {}),
    signWithParams: `/v /debug /dlib ${process.env.AZURE_CODE_SIGNING_DLIB} /dmdf ${process.env.AZURE_METADATA_JSON}`,
    timestampServer: "http://timestamp.acs.microsoft.com",
    hashes: ["sha256"],
  };
}

const windowsSign = azureWindowsSigning();

function removeUnusedMacPermissions(buildPath, _electronVersion, platform, _arch, callback) {
  if (platform !== "darwin") return callback();
  try {
    const contents = path.resolve(buildPath, "..", "..");
    const pending = [contents];
    while (pending.length) {
      const current = pending.pop();
      for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
        const child = path.join(current, entry.name);
        if (entry.isDirectory()) pending.push(child);
        else if (entry.name === "Info.plist") {
          const info = plist.parse(fs.readFileSync(child, "utf8"));
          for (const key of [
            "NSAudioCaptureUsageDescription",
            "NSBluetoothAlwaysUsageDescription",
            "NSBluetoothPeripheralUsageDescription",
            "NSCameraUsageDescription",
            "NSMicrophoneUsageDescription",
          ]) delete info[key];
          if (child === path.join(contents, "Info.plist")) delete info.NSAppTransportSecurity;
          fs.writeFileSync(child, plist.build(info));
        }
      }
    }
    callback();
  } catch (error) {
    callback(error);
  }
}

module.exports = {
  packagerConfig: {
    name: "Clippi-Health",
    executableName: "Clippi-Health",
    appBundleId: "io.github.bennydogg.clippihealth",
    appCategoryType: "public.app-category.medical",
    appCopyright: "Copyright Clippi-Health contributors",
    asar: true,
    icon: platformIcon,
    extraResource: [path.resolve(__dirname, "runtime", "clippi-runtime")],
    ignore: [/^\/(?!dist(?:\/|$)|package\.json$)/, /\.map$/],
    osxSign: process.env.MACOS_SIGN_IDENTITY
      ? { identity: process.env.MACOS_SIGN_IDENTITY, continueOnError: false }
      : undefined,
    osxNotarize: macNotarization(),
    windowsSign,
    afterCopy: [removeUnusedMacPermissions],
  },
  makers: [
    {
      name: "@electron-forge/maker-dmg",
      platforms: ["darwin"],
      config: {
        name: "Clippi-Health",
        icon: path.join(assets, "clippi-health.icns"),
        format: "ULFO",
      },
    },
    {
      name: "@electron-forge/maker-squirrel",
      platforms: ["win32"],
      config: {
        name: "ClippiHealth",
        authors: "Clippi-Health contributors",
        description: "Private, local health-record organizer",
        setupIcon: path.join(assets, "clippi-health.ico"),
        iconUrl: "https://raw.githubusercontent.com/bennydogg/clippi-health/main/assets/icons/clippi-health.ico",
        ...(windowsSign ? { windowsSign } : {}),
      },
    },
    {
      name: "@electron-forge/maker-deb",
      platforms: ["linux"],
      config: {
        options: {
          name: "clippi-health",
          bin: "Clippi-Health",
          productName: "Clippi-Health",
          maintainer: "Clippi-Health contributors",
          homepage: "https://github.com/bennydogg/clippi-health",
          icon: path.join(assets, "clippi-health.png"),
          categories: ["Utility", "MedicalSoftware"],
          depends: ["libc6 (>= 2.35)"],
        },
      },
    },
    {
      name: "@electron-forge/maker-zip",
      platforms: ["darwin", "win32", "linux"],
      config: {},
    },
  ],
  hooks: {
    postPackage: async (_config, result) => {
      if (result.platform !== "darwin" || process.env.MACOS_SIGN_IDENTITY) return;
      for (const outputPath of result.outputPaths) {
        const appPath = path.join(outputPath, "Clippi-Health.app");
        execFileSync("codesign", ["--force", "--deep", "--sign", "-", appPath], { stdio: "inherit" });
      }
    },
  },
  plugins: [
    new FusesPlugin({
      version: FuseVersion.V1,
      [FuseV1Options.RunAsNode]: false,
      [FuseV1Options.EnableCookieEncryption]: true,
      [FuseV1Options.EnableNodeOptionsEnvironmentVariable]: false,
      [FuseV1Options.EnableNodeCliInspectArguments]: false,
      [FuseV1Options.EnableEmbeddedAsarIntegrityValidation]: true,
      [FuseV1Options.OnlyLoadAppFromAsar]: true,
    }),
  ],
};
