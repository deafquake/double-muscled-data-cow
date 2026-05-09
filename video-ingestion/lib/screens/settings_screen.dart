import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../providers/settings_provider.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late TextEditingController _folderController;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final settings = context.read<SettingsProvider>();
    _folderController =
        TextEditingController(text: settings.subfolder);
  }

  @override
  void dispose() {
    _folderController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final name = _folderController.text.trim();
    if (name.isEmpty) return;

    setState(() => _saving = true);
    await context.read<SettingsProvider>().setSubfolder(name);
    if (mounted) {
      setState(() => _saving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Sync folder updated'),
          duration: Duration(seconds: 2),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final settings = context.watch<SettingsProvider>();

    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        leading: const BackButton(color: Colors.white),
        title: const Text(
          'Settings',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          // ── Sync folder section ──────────────────────────────────────
          const _SectionHeader('Sync Folder'),
          const SizedBox(height: 8),
          const Text(
            'Choose a subfolder name inside this app\'s Documents directory. '
            'Point Mobius Sync at the full path shown below.',
            style: TextStyle(color: Colors.white54, fontSize: 13, height: 1.5),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _folderController,
            style: const TextStyle(color: Colors.white),
            decoration: InputDecoration(
              labelText: 'Subfolder name',
              labelStyle: const TextStyle(color: Colors.white54),
              hintText: 'e.g. MobiusVideos',
              hintStyle: const TextStyle(color: Colors.white24),
              filled: true,
              fillColor: Colors.white10,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: BorderSide.none,
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide:
                    const BorderSide(color: Color(0xFF1A73E8), width: 2),
              ),
            ),
            inputFormatters: [
              FilteringTextInputFormatter.allow(RegExp(r'[\w\-. ]')),
            ],
            onSubmitted: (_) => _save(),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: _saving ? null : _save,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF1A73E8),
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10)),
              ),
              child: _saving
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: Colors.white),
                    )
                  : const Text('Save',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
            ),
          ),

          const SizedBox(height: 32),

          // ── Full path card ───────────────────────────────────────────
          const _SectionHeader('Current Sync Path'),
          const SizedBox(height: 8),
          _PathCard(path: settings.syncFolderPath),

          const SizedBox(height: 32),

          // ── How to connect Mobius Sync ───────────────────────────────
          const _SectionHeader('How to connect Mobius Sync'),
          const SizedBox(height: 12),
          ..._instructions.map((step) => _InstructionRow(step)),
        ],
      ),
    );
  }
}

const _instructions = [
  (
    '1',
    'Open Mobius Sync on your iPhone.',
  ),
  (
    '2',
    'Tap + to add a new sync folder.',
  ),
  (
    '3',
    'Choose "Use a folder on this device" and browse to:\n'
        'Files → On My iPhone → Video Ingestion → <your subfolder>',
  ),
  (
    '4',
    'Pair the folder with the matching folder on your self-hosted '
        'Syncthing server using the Device ID.',
  ),
  (
    '5',
    'Every video you record will now appear in that folder and sync '
        'automatically.',
  ),
];

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader(this.title);

  @override
  Widget build(BuildContext context) => Text(
        title,
        style: const TextStyle(
          color: Color(0xFF1A73E8),
          fontSize: 12,
          fontWeight: FontWeight.w700,
          letterSpacing: 1.1,
        ),
      );
}

class _PathCard extends StatelessWidget {
  final String path;
  const _PathCard({required this.path});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white10,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(
              path,
              style: const TextStyle(
                color: Colors.white70,
                fontSize: 12,
                fontFamily: 'monospace',
              ),
            ),
          ),
          const SizedBox(width: 8),
          IconButton(
            icon: const Icon(Icons.copy, color: Colors.white38, size: 20),
            onPressed: () {
              Clipboard.setData(ClipboardData(text: path));
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Path copied to clipboard'),
                  duration: Duration(seconds: 2),
                ),
              );
            },
          ),
        ],
      ),
    );
  }
}

class _InstructionRow extends StatelessWidget {
  final (String, String) step;
  const _InstructionRow(this.step);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 24,
            height: 24,
            decoration: const BoxDecoration(
              color: Color(0xFF1A73E8),
              shape: BoxShape.circle,
            ),
            child: Center(
              child: Text(
                step.$1,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              step.$2,
              style: const TextStyle(
                  color: Colors.white70, fontSize: 13, height: 1.5),
            ),
          ),
        ],
      ),
    );
  }
}
