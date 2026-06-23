import 'package:flutter/material.dart';

import 'screens/dashboard_screen.dart';
import 'theme/app_theme.dart';

void main() {
  runApp(const RegimeTrendApp());
}

class RegimeTrendApp extends StatelessWidget {
  const RegimeTrendApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '金融雷达',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark(),
      home: const DashboardScreen(),
    );
  }
}
