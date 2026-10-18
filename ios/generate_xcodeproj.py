"""Generate ios/Kinwise.xcodeproj from the Swift sources."""

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "Kinwise"
PROJECT = ROOT / "Kinwise.xcodeproj"


def uid(seed: str) -> str:
    return hashlib.sha1(seed.encode()).hexdigest()[:24].upper()


def main() -> None:
    swift_files = sorted(SOURCE.rglob("*.swift"))
    folders = {SOURCE}
    for path in swift_files:
        current = path.parent
        while current not in folders and SOURCE in current.parents or current == SOURCE:
            folders.add(current)
            if current == SOURCE:
                break
            current = current.parent
    folders.add(SOURCE / "Resources")

    objects: list[str] = []
    build_file_lines = []
    file_ref_lines = []
    group_children: dict[Path, list[str]] = {folder: [] for folder in folders}

    def add_file(folder: Path, name: str, kind: str, key: str, sources: bool = False, resources: bool = False) -> None:
        file_id = uid("file:" + key)
        file_ref_lines.append(
            f"\t\t{file_id} /* {name} */ = {{isa = PBXFileReference; lastKnownFileType = {kind}; path = {name}; sourceTree = \"<group>\"; }};"
        )
        group_children[folder].append(f"{file_id} /* {name} */")
        if sources or resources:
            build_id = uid("build:" + key)
            build_file_lines.append(
                f"\t\t{build_id} /* {name} in {'Sources' if sources else 'Resources'} */ = {{isa = PBXBuildFile; fileRef = {file_id} /* {name} */; }};"
            )
            return build_id
        return None

    source_build_ids = []
    for path in swift_files:
        build_id = add_file(path.parent, path.name, "sourcecode.swift", path.relative_to(SOURCE).as_posix(), sources=True)
        source_build_ids.append((build_id, path.name))
    add_file(SOURCE / "Resources", "Info.plist", "text.plist.xml", "Info.plist")
    assets_build = add_file(
        SOURCE / "Resources",
        "Assets.xcassets",
        "folder.assetcatalog",
        "Assets.xcassets",
        resources=True,
    )

    group_ids = {folder: uid("group:" + folder.relative_to(SOURCE).as_posix() if folder != SOURCE else "root") for folder in folders}
    for folder, group_id in sorted(group_ids.items(), key=lambda item: len(item[0].parts)):
        for child in folders:
            if child.parent == folder:
                group_children[folder].append(f"{group_ids[child]} /* {child.name} */")

    group_blocks = []
    for folder, group_id in group_ids.items():
        name = "Kinwise" if folder == SOURCE else folder.name
        kids = "\n".join(f"\t\t\t\t{child}," for child in group_children[folder])
        group_blocks.append(
            f"""\t\t{group_id} /* {name} */ = {{
			isa = PBXGroup;
			children = (
{kids}
			);
			path = {name if folder != SOURCE else "Kinwise"};
			sourceTree = "<group>";
		}};"""
        )

    product = uid("product")
    products_group = uid("group:products")
    main_group = uid("group:main")
    sources_phase = uid("phase:sources")
    resources_phase = uid("phase:resources")
    frameworks_phase = uid("phase:frameworks")
    target = uid("target")
    project = uid("project")
    project_list = uid("configlist:project")
    target_list = uid("configlist:target")
    configs = {
        "project-debug": uid("cfg:pd"),
        "project-release": uid("cfg:pr"),
        "target-debug": uid("cfg:td"),
        "target-release": uid("cfg:tr"),
    }
    file_ref_lines.append(
        f"\t\t{product} /* Kinwise.app */ = {{isa = PBXFileReference; explicitFileType = wrapper.application; includeInIndex = 0; path = Kinwise.app; sourceTree = BUILT_PRODUCTS_DIR; }};"
    )
    source_phase_files = "\n".join(f"\t\t\t\t{build_id} /* {name} in Sources */," for build_id, name in source_build_ids)

    pbx = f"""// !$*UTF8*$!
{{
	archiveVersion = 1;
	classes = {{}};
	objectVersion = 60;
	objects = {{

/* Begin PBXBuildFile section */
{chr(10).join(build_file_lines)}
/* End PBXBuildFile section */

/* Begin PBXFileReference section */
{chr(10).join(file_ref_lines)}
/* End PBXFileReference section */

/* Begin PBXFrameworksBuildPhase section */
		{frameworks_phase} = {{isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0; }};
/* End PBXFrameworksBuildPhase section */

/* Begin PBXGroup section */
{chr(10).join(group_blocks)}
		{products_group} = {{
			isa = PBXGroup;
			children = (
				{product} /* Kinwise.app */,
			);
			name = Products;
			sourceTree = "<group>";
		}};
		{main_group} = {{
			isa = PBXGroup;
			children = (
				{group_ids[SOURCE]} /* Kinwise */,
				{products_group} /* Products */,
			);
			sourceTree = "<group>";
		}};
/* End PBXGroup section */

/* Begin PBXNativeTarget section */
		{target} /* Kinwise */ = {{
			isa = PBXNativeTarget;
			buildConfigurationList = {target_list};
			buildPhases = (
				{sources_phase},
				{frameworks_phase},
				{resources_phase},
			);
			buildRules = ();
			dependencies = ();
			name = Kinwise;
			productName = Kinwise;
			productReference = {product};
			productType = "com.apple.product-type.application";
		}};
/* End PBXNativeTarget section */

/* Begin PBXProject section */
		{project} = {{
			isa = PBXProject;
			attributes = {{ LastUpgradeCheck = 1600; }};
			buildConfigurationList = {project_list};
			compatibilityVersion = "Xcode 15.0";
			developmentRegion = en;
			hasScannedForEncodings = 0;
			knownRegions = (en, Base);
			mainGroup = {main_group};
			productRefGroup = {products_group};
			projectDirPath = "";
			projectRoot = "";
			targets = ({target});
		}};
/* End PBXProject section */

/* Begin PBXResourcesBuildPhase section */
		{resources_phase} = {{
			isa = PBXResourcesBuildPhase;
			buildActionMask = 2147483647;
			files = (
				{assets_build} /* Assets.xcassets in Resources */,
			);
			runOnlyForDeploymentPostprocessing = 0;
		}};
/* End PBXResourcesBuildPhase section */

/* Begin PBXSourcesBuildPhase section */
		{sources_phase} = {{
			isa = PBXSourcesBuildPhase;
			buildActionMask = 2147483647;
			files = (
{source_phase_files}
			);
			runOnlyForDeploymentPostprocessing = 0;
		}};
/* End PBXSourcesBuildPhase section */

/* Begin XCBuildConfiguration section */
		{configs["project-debug"]} = {{
			isa = XCBuildConfiguration;
			buildSettings = {{
				ALWAYS_SEARCH_USER_PATHS = NO;
				CLANG_ENABLE_MODULES = YES;
				DEBUG_INFORMATION_FORMAT = dwarf;
				IPHONEOS_DEPLOYMENT_TARGET = 17.0;
				ONLY_ACTIVE_ARCH = YES;
				SDKROOT = iphoneos;
				SWIFT_ACTIVE_COMPILATION_CONDITIONS = DEBUG;
				SWIFT_OPTIMIZATION_LEVEL = "-Onone";
			}};
			name = Debug;
		}};
		{configs["project-release"]} = {{
			isa = XCBuildConfiguration;
			buildSettings = {{
				ALWAYS_SEARCH_USER_PATHS = NO;
				CLANG_ENABLE_MODULES = YES;
				DEBUG_INFORMATION_FORMAT = "dwarf-with-dsym";
				IPHONEOS_DEPLOYMENT_TARGET = 17.0;
				SDKROOT = iphoneos;
				SWIFT_COMPILATION_MODE = wholemodule;
				VALIDATE_PRODUCT = YES;
			}};
			name = Release;
		}};
		{configs["target-debug"]} = {{
			isa = XCBuildConfiguration;
			buildSettings = {{
				ASSETCATALOG_COMPILER_APPICON_NAME = AppIcon;
				ASSETCATALOG_COMPILER_GLOBAL_ACCENT_COLOR_NAME = AccentColor;
				CODE_SIGN_STYLE = Automatic;
				CURRENT_PROJECT_VERSION = 1;
				GENERATE_INFOPLIST_FILE = YES;
				INFOPLIST_FILE = Kinwise/Resources/Info.plist;
				INFOPLIST_KEY_CFBundleDisplayName = Kinwise;
				INFOPLIST_KEY_UIApplicationSceneManifest_Generation = YES;
				INFOPLIST_KEY_UISupportedInterfaceOrientations_iPad = "UIInterfaceOrientationPortrait UIInterfaceOrientationPortraitUpsideDown UIInterfaceOrientationLandscapeLeft UIInterfaceOrientationLandscapeRight";
				INFOPLIST_KEY_UISupportedInterfaceOrientations_iPhone = UIInterfaceOrientationPortrait;
				LD_RUNPATH_SEARCH_PATHS = "$(inherited) @executable_path/Frameworks";
				MARKETING_VERSION = 0.1.0;
				PRODUCT_BUNDLE_IDENTIFIER = com.kinwise.app;
				PRODUCT_NAME = "$(TARGET_NAME)";
				SUPPORTED_PLATFORMS = "iphoneos iphonesimulator";
				SUPPORTS_MACCATALYST = NO;
				SWIFT_VERSION = 6.0;
				TARGETED_DEVICE_FAMILY = "1,2";
			}};
			name = Debug;
		}};
		{configs["target-release"]} = {{
			isa = XCBuildConfiguration;
			buildSettings = {{
				ASSETCATALOG_COMPILER_APPICON_NAME = AppIcon;
				ASSETCATALOG_COMPILER_GLOBAL_ACCENT_COLOR_NAME = AccentColor;
				CODE_SIGN_STYLE = Automatic;
				CURRENT_PROJECT_VERSION = 1;
				GENERATE_INFOPLIST_FILE = YES;
				INFOPLIST_FILE = Kinwise/Resources/Info.plist;
				INFOPLIST_KEY_CFBundleDisplayName = Kinwise;
				INFOPLIST_KEY_UIApplicationSceneManifest_Generation = YES;
				INFOPLIST_KEY_UISupportedInterfaceOrientations_iPad = "UIInterfaceOrientationPortrait UIInterfaceOrientationPortraitUpsideDown UIInterfaceOrientationLandscapeLeft UIInterfaceOrientationLandscapeRight";
				INFOPLIST_KEY_UISupportedInterfaceOrientations_iPhone = UIInterfaceOrientationPortrait;
				LD_RUNPATH_SEARCH_PATHS = "$(inherited) @executable_path/Frameworks";
				MARKETING_VERSION = 0.1.0;
				PRODUCT_BUNDLE_IDENTIFIER = com.kinwise.app;
				PRODUCT_NAME = "$(TARGET_NAME)";
				SUPPORTED_PLATFORMS = "iphoneos iphonesimulator";
				SUPPORTS_MACCATALYST = NO;
				SWIFT_VERSION = 6.0;
				TARGETED_DEVICE_FAMILY = "1,2";
			}};
			name = Release;
		}};
/* End XCBuildConfiguration section */

/* Begin XCConfigurationList section */
		{project_list} = {{
			isa = XCConfigurationList;
			buildConfigurations = (
				{configs["project-debug"]} /* Debug */,
				{configs["project-release"]} /* Release */,
			);
			defaultConfigurationIsVisible = 0;
			defaultConfigurationName = Release;
		}};
		{target_list} = {{
			isa = XCConfigurationList;
			buildConfigurations = (
				{configs["target-debug"]} /* Debug */,
				{configs["target-release"]} /* Release */,
			);
			defaultConfigurationIsVisible = 0;
			defaultConfigurationName = Release;
		}};
/* End XCConfigurationList section */
	}};
	rootObject = {project};
}}
"""
    PROJECT.mkdir(exist_ok=True)
    (PROJECT / "project.pbxproj").write_text(pbx)
    print(f"Wrote {PROJECT / 'project.pbxproj'} ({len(swift_files)} Swift files)")


if __name__ == "__main__":
    main()
