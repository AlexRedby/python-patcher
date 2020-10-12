from __future__ import unicode_literals

import os

import common

try:
	from typing import List, Optional, Dict, Set
except:
	pass # Just needed for pycharm comments


def getUnityVersion(datadir, verbosePrinting=True):
	# type: (str, bool) -> str
	"""
	Given the datadir of a Higurashi game (like 'HigurashiEp0X_Data'), returns the unity version of the game
	Raises an exeption if:
	- The `HigurashiEp0X_Data/resources.assets` file is missing (raises MissingAssetsBundleException)
	- The `HigurashiEp0X_Data/resources.assets` bundle failed to open (raises error from open() call or read() call)
	- The Unity version was too old (raises OldUnityException)
	"""
	assetsbundlePath = os.path.join(datadir, "resources.assets")
	if not os.path.exists(assetsbundlePath):
		raise MissingAssetsBundleException(assetsbundlePath)

	with open(assetsbundlePath, "rb") as assetsBundle:
		unityVersion = assetsBundle.read(28)[20:].decode("utf-8").rstrip("\0")
		if verbosePrinting:
			print("Unity Version: Read [{}] from [{}]".format(unityVersion, assetsbundlePath))
		if int(unityVersion.split('.')[0]) < 5:
			raise OldUnityException(unityVersion)
		return unityVersion

class FullInstallConfiguration:
	# contains all the install information required to install the game to a given path

	def __init__(self, subModConfig, path, isSteam):
		# type: (SubModConfig, str, bool) -> None
		self.subModConfig = subModConfig # type: SubModConfig
		self.installPath = path # type: str
		self.isSteam = isSteam # type: bool
		self.useIPV6 = False
		self.unityVersion = None

	#applies the fileOverrides to the files to
	def buildFileListSorted(self, datadir="", verbosePrinting=True):
		# type: (str, bool) -> List[ModFile]
		# convert the files list into a dict
		filesDict = {}
		for file in self.subModConfig.files:
			filesDict[file.name] = file

		if datadir:
			unityVersion = getUnityVersion(datadir, verbosePrinting)
		else:
			unityVersion = None
			print("Unity Version: [{}/Not a Unity game]".format(unityVersion))

		for fileOverride in self.subModConfig.fileOverrides:
			# skip overrides where OS doesn't match
			if common.Globals.OS_STRING not in fileOverride.os:
				continue

			# skip overrides where isSteam doesn't match (NOTE: 'steam' can be null, which means that any type is acceptable
			if fileOverride.steam is not None and fileOverride.steam != self.isSteam:
				continue

			if fileOverride.unity is not None and fileOverride.unity != unityVersion:
				continue

			# for all other overrides, overwrite the value in the filesDict with a new ModFile
			currentModFile = filesDict[fileOverride.name]
			filesDict[fileOverride.name] = ModFile(currentModFile.name, fileOverride.url, currentModFile.priority, id=fileOverride.id)

		# Look for override-required files that weren't overridden
		for key, value in filesDict.items():
			if value.url is not None:
				continue
			candidates = [x for x in self.subModConfig.fileOverrides if x.name == key and common.Globals.OS_STRING in x.os]
			raise FailedFileOverrideException(key, candidates, unity=unityVersion, steam=self.isSteam)

		# Save the unity version for future use
		self.unityVersion = unityVersion

		# Pre-sort by the file's native order, to ensure deterministic ordering for files with the same priority
		overriddenFiles = sorted(filesDict.values(), key=lambda x: x.nativeOrder)

		# sort the priority from Lowest to Highest (eg items with priority '0' will always be at start of the list)
		# this is because the low priority items should be extracted first, so the high priority items can overwrite them.
		return sorted(overriddenFiles, key=lambda x: x.priority)


class ModFile:
	modFileCounter = 0
	def __init__(self, name, url, priority, id=None):
		# type: (str, Optional[str], int, str) -> None
		self.name = name
		self.url = url

		self.id = self.name if id is None else id

		# NOTE: the 'priority' indicates the order of extraction:
		# Files are extracted in order 0,1,2,3 ...
		# Therefore, the 'later extracted' files are higher priority, that is archives with priority 3 will overwrite priority 0,1,2 archives
		self.priority = priority #consider renaming this "extractionOrder"?

		# This variable is used to provide ordering which roughly matches the ordering in the JSON file
		# to ensure files are downloaded and extracted in a deterministic manner
		self.nativeOrder = ModFile.modFileCounter
		ModFile.modFileCounter += 1


class ModFileOverride:
	def __init__(self, name, id, os, steam, unity, url):
		# type: (str, str, List[str], Optional[bool], Optional[str], str) -> None
		self.name = name # type: str
		self.id = id
		"""A unique identifier among all files and modfiles for this submod. Set manually as 'movie-unix' for example"""
		self.os = os # type: List[str]
		"""This is an List, describing all operating systems where this override applies eg ["mac", "linux"]"""
		self.steam = steam	#type: Optional[bool]
		"""This can be 'None' if the override applies to both mac and steam"""
		self.unity = unity #type: Optional[str]
		self.url = url # type: str


class ModOption:
	def __init__(self, name, description, group, type, isRadio, data, isGlobal=False):
		self.id = group + ': ' + name # type: str # unique ID for each mod option, for example "SE Options-Old OST"
		self.name = name # type: str
		self.description = description # type: str
		"""A textual description of the mod option, only used for display"""
		self.group = group # type: str
		"""Defined at Group Level: This defines what named group the mod option is categorized under"""
		self.type = type # type: str
		"""Defined at Group Level: This is the type of mod option. It can be used instead of the (group, name) pair to filter out actions.
		For example, all mod options of type 'downloadAndExtract' type should contain a 'url' and 'relativeExtractionPath'
		field in their data dictionary, and thus can be processed in python the same way."""
		self.isRadio = isRadio # type: bool
		"""Defines whether the option is """
		self.data = data # type: dict
		"""This contains any data required to execute this mod option. It is deliberately an untyped dict to
		accommodate various kinds of fields/data required by various kinds of options. You must refer to the JSON to
		check what kinds of values it contains for a given type of mod option."""
		self.value = False # type: bool
		"""This represents whether the user has enabled or disabled this mod option"""
		self.isGlobal = isGlobal # type: bool
		"""Options which should be remembered/mirrored across different game families should be set as globalOptions
		For example, a 'download only' or 'french patch' option should be remembered across Umineko and Higurashi
		Options are considered 'the same' if they have the same id
		Note that options within the same family are automatically remembered/mirrored, regardless of this 'isGlobal' value
		"""
	def __repr__(self):
		return "Option ID: [{}] Value: [{}]".format(self.id, self.value)


class DownloadAndExtractOption:
	def __init__(self, name, description, url, relativeExtractionPath, priority):
		self.name = name # type: str
		self.description = description # type: str
		self.url = url # type: str
		self.relativeExtractionPath = relativeExtractionPath # type: str
		self.priority = priority # type: int


class ModOptionParser:
	def __init__(self, fullInstallConfiguration):
		self.config = fullInstallConfiguration # type: FullInstallConfiguration
		self.downloadAndExtractOptionsByPriority = [] # type: List[DownloadAndExtractOption]
		self.keepDownloads = False
		self.installSteamGrid = False
		self.partialManualInstall = False

		# Sort according to priority - higher priority items will be extracted later, overwriting lower priority items.
		for modOption in self.config.subModConfig.modOptions:
			if modOption.value:
				if modOption.type == 'downloadAndExtract' and modOption.data is not None:
					self.downloadAndExtractOptionsByPriority.append(
						DownloadAndExtractOption(
							modOption.name,
							modOption.description,
							modOption.data['url'],
							modOption.data['relativeExtractionPath'],
							modOption.data['priority']
						)
					)
				elif modOption.type == 'keepDownloads':
					self.keepDownloads = True
				elif modOption.type == 'installSteamGrid':
					self.installSteamGrid = True
				elif modOption.type == 'partialManualInstall':
					self.partialManualInstall = True

		# Make sure download and extraction options are sorted
		self.downloadAndExtractOptionsByPriority.sort(key=lambda opt: opt.priority)


class SubModConfig:
	# directly represents a single submod from the json file

	subModUniqueIDCounter = 0

	#object initialized in factory func
	def __init__(self, mod, subMod):
		# Generate a unique ID for each subModConfig. This variable is not present in the JSON file.
		self.id = SubModConfig.subModUniqueIDCounter
		SubModConfig.subModUniqueIDCounter += 1

		self.family = mod['family'] # type: str
		self.modName = mod['name']  # type: str
		self.target = mod['target'] # type: str
		self.CFBundleName = mod.get('CFBundleName') # type: Optional[str]
		self.CFBundleIdentifier = mod.get('CFBundleIdentifier') # type: Optional[str]
		self.dataName = mod['dataname'] # type: str
		self.identifiers = mod['identifiers'] # type: List[str]
		self.subModName = subMod['name'] # type: str
		self.descriptionID = subMod['descriptionID'] # type: str
		"""This variable sets which description to display on the web GUI
		The actual description text is stored on the webpage, not in the JSON or python side."""

		self.files = [] # type: List[ModFile]
		for subModFile in subMod['files']:
			self.files.append(ModFile(name=subModFile['name'], url = subModFile.get('url'), priority=subModFile['priority']))

		self.fileOverrides = [] # type: List[ModFileOverride]
		for subModFileOverride in subMod['fileOverrides']:
			self.fileOverrides.append(ModFileOverride(
				name=subModFileOverride['name'],
				os=subModFileOverride['os'],
				steam=subModFileOverride.get('steam'),
				unity=subModFileOverride.get('unity'),
				url=subModFileOverride['url'],
				id=subModFileOverride['id']
			))

		# If no mod options are specified in the JSON, the 'self.modOptions' field defaults to the empty list ([])
		self.modOptions = [] # type: List[ModOption]

		def jsonAddModOptionsFromList(jsonModOptionList, isRadio):
			for jsonModOption in jsonModOptionList:
				self.modOptions.append(ModOption(name=jsonModOption['name'],
				                                 description=jsonModOption['description'],
				                                 group=jsonModOptionGroup['name'],
				                                 type=jsonModOptionGroup['type'],
				                                 isRadio=isRadio,
				                                 data=jsonModOption.get('data', None),
				                                 isGlobal=jsonModOption.get('isGlobal', False)))

		for jsonModOptionGroup in mod.get('modOptionGroups', []):
			applicableSubMods = jsonModOptionGroup.get('submods')
			if applicableSubMods is None or self.subModName in applicableSubMods:
				jsonAddModOptionsFromList(jsonModOptionGroup.get('radio', []), isRadio=True)
				jsonAddModOptionsFromList(jsonModOptionGroup.get('checkBox', []), isRadio=False)

		# Mod options which don't come from the installData.json file are added here
		installSteamGridDescription = """
This option updates the header and icon art in the Steam app to match the mod's art style. All Higurashi and Umineko games will have their icons updated, not just the game being patched.

<table class="umineko-image-table-content umineko-image-table-horizontal">
<tbody>
	<tr>
	<td>Original</td>
		<td><img src="img/steamgrid/header-original.jpg"></td>
	</tr>
	<tr>
		<td>Updated</td>
		<td><img src="img/steamgrid/header-updated.jpg"></td>
	</tr>
</tbody>
</table>
"""
		if common.Globals.IS_WINDOWS and 'voiceonly' not in self.descriptionID.lower():
			self.modOptions.append(ModOption(name="Update Steamgrid Icons",
			                                 description=installSteamGridDescription,
			                                 group="Common Options",
			                                 type="installSteamGrid",
			                                 isRadio=False,
			                                 data=None,
			                                 isGlobal=True))

		# Only show 'partial manual install' options for Higurashi for now (Umineko partial install is not implemented)
		if self.family == 'higurashi':
			self.modOptions.append(ModOption(name="Partial Manual Install",
		                                 description="""Users who get a 'Permission Denied' error should use this option to install the mod.

Please watch the instructions on using this option: [https://www.youtube.com/watch?v=Px4JWsSycQE](https://www.youtube.com/watch?v=Px4JWsSycQE)

This makes the installer download and extract the mod files to a temporary folder (shown at the end of the install). After this, **you** have to manually copy the mod files to the game directory.

You are also need to manually delete the temporary installer files (see end of video).""",
		                                 group="Experimental Options",
		                                 type="partialManualInstall",
		                                 isRadio=False,
		                                 data=None,
		                                 isGlobal=True))

	def __repr__(self):
		return "Type: [{}] Game Name: [{}]".format(self.modName, self.subModName)

	# Submod lists may contain many entries with the same modName (eg a list may have [umi-question:voice, umi-question:full, umi-question:full])
	# This function gets the unique modNames. It also preserves the original order of the list.
	@staticmethod
	def getUniqueModNamesInSubModList(subModList):
		# type: ([SubModConfig]) -> [str]
		uniqueModNames = []
		alreadySeenNames = set()
		for subMod in subModList:
			if subMod.modName not in alreadySeenNames:
				uniqueModNames.append(subMod.modName)
				alreadySeenNames.add(subMod.modName)

		return uniqueModNames

	def printEnabledOptions(self):
		print('\nEnabled Mod Options:')

		numberEnabled = 0
		for modOption in self.modOptions:
			if modOption.value:
				print('  - {}: {}'.format(modOption.group, modOption.name))
				numberEnabled += 1

		if numberEnabled == 0:
			print(' - No options were enabled.')

		print()

class OldUnityException(Exception):
	def __init__(self, version):
		# type: (str) -> None
		self.version = version # type: str

	def __str__(self):
		return "Your game uses Unity "  + self.version + " which isn't supported by this mod.  Please update your game to a newer version."


class FailedFileOverrideException(Exception):
	def __init__(self, name, candidates, unity, steam):
		# type: (str, List[ModFileOverride], Optional[str], bool) -> None
		self.name = name
		self.candidates = candidates # type: List[ModFileOverride]
		self.unity = unity
		self.steam = steam

	def describe(self, candidate):
		# type: (ModFileOverride) -> str
		out = "("
		if candidate.steam is not None:
			out += "steam: {}".format(candidate.steam)
		if candidate.unity is not None:
			if len(out) > 1:
				out += ", "
			out += "unity: " + candidate.unity
		return out + ")"

	def __str__(self):
		if not self.candidates:
			return "Your current OS is not supported by the file {} in this mod".format(self.name)
		hasUnity = any(x.unity is not None for x in self.candidates)
		out = "Failed to find a {} file to use, your game has the properties (steam: {}".format(self.name, self.steam)
		if hasUnity:
			out += ", unity: {}".format(self.unity)
		out += ") but the available versions had the requirements " + ", ".join(self.describe(candidate) for candidate in self.candidates)
		return out


class MissingAssetsBundleException(Exception):
	def __init__(self, assetsbundlePath):
		# type: (str) -> None
		self.assetsbundlePath = assetsbundlePath  # type: str

	def __str__(self):
		return "Can't determine Unity version - missing `resources.assets` file [{}].\n\n" \
		       "You probably need to re-install the game, or ask for help on our Discord.".format(self.assetsbundlePath)
