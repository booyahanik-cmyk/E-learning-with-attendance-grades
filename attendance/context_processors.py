def pending_corrections(request):
    """Context processor providing pending attendance correction request counts for faculty."""
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {'pending_corrections_count': 0}
    
    try:
        from .models import AttendanceCorrectionRequest
        if request.user.role == 'faculty':
            count = AttendanceCorrectionRequest.objects.filter(
                teacher=request.user,
                status=AttendanceCorrectionRequest.Status.PENDING
            ).count()
            return {'pending_corrections_count': count}
        elif request.user.role == 'admin' or request.user.is_superuser:
            count = AttendanceCorrectionRequest.objects.filter(
                status=AttendanceCorrectionRequest.Status.PENDING
            ).count()
            return {'pending_corrections_count': count}
    except Exception:
        pass
    
    return {'pending_corrections_count': 0}
