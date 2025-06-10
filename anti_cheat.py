import json
import time
from datetime import datetime
from flask import request, current_app
from app import db
from models import AntiCheatLog, TestResult

class AntiCheatService:
    """Anti-cheat monitoring and enforcement service"""
    
    def __init__(self):
        self.violation_types = {
            'tab_switch': 'Tab switching detected',
            'copy_paste': 'Copy/paste attempt detected',
            'right_click': 'Right-click disabled violation',
            'inspect': 'Developer tools access attempt',
            'fullscreen_exit': 'Fullscreen mode exit detected',
            'focus_loss': 'Window focus loss detected',
            'webcam_disconnect': 'Webcam disconnected',
            'multiple_faces': 'Multiple faces detected in webcam',
            'no_face': 'No face detected in webcam',
            'suspicious_behavior': 'Suspicious behavior pattern detected',
            'network_change': 'Network/IP address change detected',
            'time_manipulation': 'System time manipulation detected'
        }
        
        self.severity_levels = {
            'low': ['focus_loss', 'webcam_disconnect'],
            'medium': ['tab_switch', 'fullscreen_exit', 'no_face'],
            'high': ['copy_paste', 'right_click', 'inspect', 'multiple_faces', 'suspicious_behavior', 'network_change', 'time_manipulation']
        }
    
    def log_violation(self, test_result_id, violation_type, description='', ip_address=None, user_agent=None):
        """Log an anti-cheat violation"""
        try:
            severity = self._get_violation_severity(violation_type)
            
            log_entry = AntiCheatLog(
                test_result_id=test_result_id,
                violation_type=violation_type,
                description=description or self.violation_types.get(violation_type, 'Unknown violation'),
                severity=severity,
                ip_address=ip_address or request.remote_addr,
                user_agent=user_agent or request.headers.get('User-Agent', '')
            )
            
            db.session.add(log_entry)
            db.session.commit()
            
            # Check if test should be terminated
            violation_count = self._get_violation_count(test_result_id, severity)
            action = self._determine_action(violation_count, severity)
            
            current_app.logger.warning(f"Anti-cheat violation: {violation_type} for test {test_result_id}")
            
            return {
                'logged': True,
                'severity': severity,
                'action': action,
                'violation_count': violation_count
            }
            
        except Exception as e:
            current_app.logger.error(f"Error logging anti-cheat violation: {str(e)}")
            return {'logged': False, 'error': str(e)}
    
    def _get_violation_severity(self, violation_type):
        """Determine severity level of violation"""
        for severity, types in self.severity_levels.items():
            if violation_type in types:
                return severity
        return 'medium'  # default
    
    def _get_violation_count(self, test_result_id, severity=None):
        """Get violation count for a test result"""
        query = AntiCheatLog.query.filter_by(test_result_id=test_result_id)
        
        if severity:
            query = query.filter_by(severity=severity)
        
        return query.count()
    
    def _determine_action(self, violation_count, severity):
        """Determine what action to take based on violations"""
        if severity == 'high':
            if violation_count >= 2:
                return 'terminate_test'
            elif violation_count >= 1:
                return 'final_warning'
        
        elif severity == 'medium':
            if violation_count >= 3:
                return 'terminate_test'
            elif violation_count >= 2:
                return 'final_warning'
            else:
                return 'warning'
        
        else:  # low severity
            if violation_count >= 5:
                return 'warning'
        
        return 'log_only'
    
    def get_test_violations(self, test_result_id):
        """Get all violations for a test"""
        violations = AntiCheatLog.query.filter_by(test_result_id=test_result_id).order_by(
            AntiCheatLog.timestamp.desc()
        ).all()
        
        return [{
            'type': v.violation_type,
            'description': v.description,
            'severity': v.severity,
            'timestamp': v.timestamp.isoformat(),
            'ip_address': v.ip_address
        } for v in violations]
    
    def get_violation_summary(self, test_result_id):
        """Get violation summary for a test"""
        violations = AntiCheatLog.query.filter_by(test_result_id=test_result_id).all()
        
        summary = {
            'total_violations': len(violations),
            'high_severity': 0,
            'medium_severity': 0,
            'low_severity': 0,
            'violation_types': {},
            'risk_level': 'low'
        }
        
        for violation in violations:
            # Count by severity
            if violation.severity == 'high':
                summary['high_severity'] += 1
            elif violation.severity == 'medium':
                summary['medium_severity'] += 1
            else:
                summary['low_severity'] += 1
            
            # Count by type
            v_type = violation.violation_type
            summary['violation_types'][v_type] = summary['violation_types'].get(v_type, 0) + 1
        
        # Determine risk level
        if summary['high_severity'] >= 2 or summary['medium_severity'] >= 3:
            summary['risk_level'] = 'high'
        elif summary['high_severity'] >= 1 or summary['medium_severity'] >= 2:
            summary['risk_level'] = 'medium'
        
        return summary
    
    def validate_test_environment(self, test_result_id, environment_data):
        """Validate test environment data"""
        try:
            # Check for suspicious patterns
            violations = []
            
            # Screen resolution changes
            if 'screen_changes' in environment_data and environment_data['screen_changes'] > 2:
                violations.append({
                    'type': 'suspicious_behavior',
                    'description': f"Multiple screen resolution changes detected: {environment_data['screen_changes']}"
                })
            
            # Network changes
            if 'ip_changes' in environment_data and environment_data['ip_changes'] > 0:
                violations.append({
                    'type': 'network_change',
                    'description': f"IP address changes detected: {environment_data['ip_changes']}"
                })
            
            # Time inconsistencies
            if 'time_jumps' in environment_data and environment_data['time_jumps'] > 0:
                violations.append({
                    'type': 'time_manipulation',
                    'description': f"System time manipulation detected: {environment_data['time_jumps']} jumps"
                })
            
            # Log all detected violations
            for violation in violations:
                self.log_violation(
                    test_result_id,
                    violation['type'],
                    violation['description']
                )
            
            return {
                'valid': len(violations) == 0,
                'violations': violations
            }
            
        except Exception as e:
            current_app.logger.error(f"Error validating test environment: {str(e)}")
            return {'valid': False, 'error': str(e)}
    
    def get_proctoring_config(self, assessment):
        """Get proctoring configuration for an assessment"""
        try:
            anti_cheat_rules = assessment.get_anti_cheat_rules()
            
            config = {
                'webcam_required': anti_cheat_rules.get('webcam_required', True),
                'fullscreen_required': anti_cheat_rules.get('fullscreen_required', True),
                'copy_paste_disabled': not anti_cheat_rules.get('copy_paste_allowed', False),
                'right_click_disabled': anti_cheat_rules.get('right_click_disabled', True),
                'tab_switching_disabled': not anti_cheat_rules.get('tab_switching_allowed', False),
                'inspect_disabled': anti_cheat_rules.get('inspect_disabled', True),
                'screenshot_disabled': anti_cheat_rules.get('screenshot_disabled', True),
                'max_violations': anti_cheat_rules.get('max_violations', 3),
                'warning_enabled': anti_cheat_rules.get('violation_warning', True),
                'face_detection': True,
                'multiple_face_detection': True,
                'gaze_tracking': False,  # Advanced feature
                'keystroke_analysis': False  # Advanced feature
            }
            
            return config
            
        except Exception as e:
            current_app.logger.error(f"Error getting proctoring config: {str(e)}")
            return self._get_default_proctoring_config()
    
    def _get_default_proctoring_config(self):
        """Get default proctoring configuration"""
        return {
            'webcam_required': True,
            'fullscreen_required': True,
            'copy_paste_disabled': True,
            'right_click_disabled': True,
            'tab_switching_disabled': True,
            'inspect_disabled': True,
            'screenshot_disabled': True,
            'max_violations': 3,
            'warning_enabled': True,
            'face_detection': True,
            'multiple_face_detection': True,
            'gaze_tracking': False,
            'keystroke_analysis': False
        }
    
    def analyze_test_integrity(self, test_result_id):
        """Analyze overall test integrity"""
        try:
            violations = self.get_violation_summary(test_result_id)
            test_result = TestResult.query.get(test_result_id)
            
            if not test_result:
                return {'integrity': 'unknown', 'confidence': 0}
            
            # Calculate integrity score
            integrity_score = 100
            
            # Deduct points for violations
            integrity_score -= violations['high_severity'] * 30
            integrity_score -= violations['medium_severity'] * 15
            integrity_score -= violations['low_severity'] * 5
            
            # Additional factors
            if test_result.time_taken:
                expected_time = test_result.assessment.time_limit
                if test_result.time_taken < expected_time * 0.3:
                    integrity_score -= 20  # Suspiciously fast completion
            
            # Determine integrity level
            if integrity_score >= 85:
                integrity_level = 'high'
            elif integrity_score >= 65:
                integrity_level = 'medium'
            elif integrity_score >= 40:
                integrity_level = 'low'
            else:
                integrity_level = 'very_low'
            
            return {
                'integrity': integrity_level,
                'score': max(0, integrity_score),
                'confidence': min(100, integrity_score + 10),
                'violations': violations,
                'recommendation': self._get_integrity_recommendation(integrity_level, violations)
            }
            
        except Exception as e:
            current_app.logger.error(f"Error analyzing test integrity: {str(e)}")
            return {'integrity': 'unknown', 'confidence': 0, 'error': str(e)}
    
    def _get_integrity_recommendation(self, integrity_level, violations):
        """Get recommendation based on integrity analysis"""
        if integrity_level == 'high':
            return "Test results appear reliable with minimal concerns."
        elif integrity_level == 'medium':
            return "Test results should be reviewed carefully. Some violations detected."
        elif integrity_level == 'low':
            return "Test results should be treated with caution. Multiple violations detected."
        else:
            return "Test results are highly questionable. Consider retesting or alternative evaluation methods."
    
    def get_global_violation_stats(self, days=30):
        """Get global violation statistics for admin dashboard"""
        try:
            from datetime import timedelta
            
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            violations = AntiCheatLog.query.filter(
                AntiCheatLog.timestamp >= cutoff_date
            ).all()
            
            stats = {
                'total_violations': len(violations),
                'by_type': {},
                'by_severity': {'high': 0, 'medium': 0, 'low': 0},
                'tests_with_violations': set(),
                'most_common_violations': []
            }
            
            for violation in violations:
                # Count by type
                v_type = violation.violation_type
                stats['by_type'][v_type] = stats['by_type'].get(v_type, 0) + 1
                
                # Count by severity
                stats['by_severity'][violation.severity] += 1
                
                # Track unique tests
                stats['tests_with_violations'].add(violation.test_result_id)
            
            # Convert set to count
            stats['tests_with_violations'] = len(stats['tests_with_violations'])
            
            # Get most common violations
            stats['most_common_violations'] = sorted(
                stats['by_type'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            
            return stats
            
        except Exception as e:
            current_app.logger.error(f"Error getting violation stats: {str(e)}")
            return {
                'total_violations': 0,
                'by_type': {},
                'by_severity': {'high': 0, 'medium': 0, 'low': 0},
                'tests_with_violations': 0,
                'most_common_violations': []
            }
