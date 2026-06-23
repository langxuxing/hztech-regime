import 'package:flutter/material.dart';

/// 六大业务模块导航。
enum RadarTab {
  wallboard,
  marketRadar,
  regimeStatus,
  eventsSignals,
  models,
  blackSwan;

  String get title => switch (this) {
        RadarTab.wallboard => '大屏总览',
        RadarTab.marketRadar => '金融雷达',
        RadarTab.regimeStatus => 'Regime 状态',
        RadarTab.eventsSignals => '事件与信号',
        RadarTab.models => '算法与模型',
        RadarTab.blackSwan => '黑天鹅预警',
      };

  String get navLabel => switch (this) {
        RadarTab.wallboard => '大屏',
        RadarTab.marketRadar => '雷达',
        RadarTab.regimeStatus => 'Regime',
        RadarTab.eventsSignals => '事件',
        RadarTab.models => '模型',
        RadarTab.blackSwan => '黑天鹅',
      };

  String get moduleId => switch (this) {
        RadarTab.wallboard => 'wallboard',
        RadarTab.marketRadar => 'market_radar',
        RadarTab.regimeStatus => 'regime_status',
        RadarTab.eventsSignals => 'events_signals',
        RadarTab.models => 'models',
        RadarTab.blackSwan => 'black_swan',
      };

  IconData get icon => switch (this) {
        RadarTab.wallboard => Icons.dashboard_outlined,
        RadarTab.marketRadar => Icons.radar_outlined,
        RadarTab.regimeStatus => Icons.hub_outlined,
        RadarTab.eventsSignals => Icons.campaign_outlined,
        RadarTab.models => Icons.psychology_outlined,
        RadarTab.blackSwan => Icons.electric_bolt_outlined,
      };

  IconData get selectedIcon => switch (this) {
        RadarTab.wallboard => Icons.dashboard_rounded,
        RadarTab.marketRadar => Icons.radar_rounded,
        RadarTab.regimeStatus => Icons.hub_rounded,
        RadarTab.eventsSignals => Icons.campaign_rounded,
        RadarTab.models => Icons.psychology_rounded,
        RadarTab.blackSwan => Icons.electric_bolt_rounded,
      };
}
