import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  static const bg = Color(0xFF0B0E14);
  static const surface = Color(0xFF121722);
  static const surfaceHigh = Color(0xFF1A2130);
  static const border = Color(0xFF2A3344);
  static const textPrimary = Color(0xFFE8EDF5);
  static const textSecondary = Color(0xFF8B95A8);
  static const long = Color(0xFF22C55E);
  static const short = Color(0xFFEF4444);
  static const neutral = Color(0xFFF59E0B);
  static const accent = Color(0xFF3B82F6);
  static const magnet = Color(0xFFA855F7);

  static ThemeData dark() {
    final base = ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: bg,
      colorScheme: const ColorScheme.dark(
        surface: surface,
        primary: accent,
        secondary: magnet,
      ),
      dividerColor: border,
      useMaterial3: true,
    );

    return base.copyWith(
      textTheme: GoogleFonts.jetBrainsMonoTextTheme(base.textTheme).apply(
        bodyColor: textPrimary,
        displayColor: textPrimary,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: bg,
        foregroundColor: textPrimary,
        elevation: 0,
        centerTitle: false,
      ),
      cardTheme: CardThemeData(
        color: surface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: border),
        ),
      ),
      iconTheme: const IconThemeData(color: textSecondary, size: 18),
    );
  }

  static Color biasColor(String bias) => switch (bias) {
        'long' => long,
        'short' => short,
        _ => neutral,
      };

  static String biasLabel(String bias) => switch (bias) {
        'long' => '做多',
        'short' => '做空',
        _ => '观望',
      };

  /// 6 象限 Regime 单元格背景色。
  static Color regimeCellColor(String? regimeId) {
    final id = (regimeId ?? '').toLowerCase();
    if (id.contains('uptrend') || id.contains('trend_up')) {
      return id.contains('high') || id.contains('mid')
          ? const Color(0xFF14532D)
          : const Color(0xFF1A3D2E);
    }
    if (id.contains('downtrend') || id.contains('trend_down')) {
      return id.contains('high') || id.contains('mid')
          ? const Color(0xFF7F1D1D)
          : const Color(0xFF312E81);
    }
    if (id.contains('fake_breakout')) return const Color(0xFF581C87);
    if (id.contains('self_heal')) return const Color(0xFF065F46);
    if (id.contains('macro_frozen')) return const Color(0xFF374151);
    if (id.contains('high_vol') || id.contains('high_vol_range')) {
      return const Color(0xFF78350F);
    }
    return const Color(0xFF1E293B);
  }

  static Color regimeTypeColor(String regime) => switch (regime) {
        'trend_up' => long,
        'trend_down' => short,
        'high_vol' => neutral,
        'macro_frozen_range' => magnet,
        'fake_breakout_wash' => short,
        'high_vol_self_heal' => long,
        _ => accent,
      };

  static Color blackSwanLevelColor(int level) => switch (level) {
        3 => short,
        2 => neutral,
        1 => accent,
        _ => textSecondary,
      };

  static String blackSwanLevelLabel(int level) => switch (level) {
        3 => '熔断挂起',
        2 => '高危预警',
        1 => '观察',
        _ => '正常推理',
      };
}
