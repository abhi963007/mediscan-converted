from rest_framework import viewsets, filters, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Patient, Consultation, Prescription, PatientDocument
from .serializers import (
    PatientSerializer, PatientPersonalUpdateSerializer, 
    ConsultationSerializer, PrescriptionSerializer, PatientDocumentSerializer
)


class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['full_name', 'uhid', 'phone']

    def get_serializer_class(self):
        if self.request.user.role == 'patient' and (self.action in ['update', 'partial_update']):
            return PatientPersonalUpdateSerializer
        return PatientSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Patient.objects.all()
        
        # Manual filtering by UHID from query params
        uhid = self.request.query_params.get('uhid')
        if uhid:
            return Patient.objects.filter(uhid=uhid)

        if user.role == 'patient' and hasattr(user, 'patient_profile'):
            return Patient.objects.filter(uhid=user.patient_profile.uhid)
        if user.role in ['receptionist', 'admin', 'hospital_admin', 'doctor']:
            return qs
        return Patient.objects.none()

    def update(self, request, *args, **kwargs):
        user = request.user
        instance = self.get_object()
        
        # Security check: patients can only edit their own
        if user.role == 'patient' and instance.user != user:
             return Response({'error': 'You can only edit your own details.'}, status=status.HTTP_403_FORBIDDEN)
             
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        user = request.user
        instance = self.get_object()
        
        # Security check: patients can only edit their own
        if user.role == 'patient' and instance.user != user:
             return Response({'error': 'You can only edit your own details.'}, status=status.HTTP_403_FORBIDDEN)
             
        return super().partial_update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        user = instance.user
        instance.delete()
        if user:
            user.delete()

    @action(detail=True, methods=['post'], url_path='treatment')
    def treatment(self, request, pk=None):
        if request.user.role != 'doctor':
            return Response({'error': 'Permission denied. Only doctors can log treatment.'}, status=status.HTTP_403_FORBIDDEN)
        
        patient = self.get_object()
        data = request.data
        
        # Create Consultation
        from .models import Consultation, Prescription
        consultation = Consultation.objects.create(
            patient=patient,
            doctor=request.user,
            hospital=request.user.hospital,
            chief_complaint=data.get('notes', ''),
            diagnosis=data.get('diagnosis', 'Pending Diagnosis'),
            treatment_plan=data.get('notes', ''),
            follow_up_date=data.get('followup_date') or None
        )
        
        # Create multiple prescriptions
        prescribed_medicines = data.get('medicines', [])
        for m_data in prescribed_medicines:
            from hospitals.models import Medicine
            medicine = Medicine.objects.get(id=m_data['id'])
            Prescription.objects.create(
                consultation=consultation,
                medicine=medicine,
                dosage=m_data.get('dosage', ''),
                instructions=m_data.get('dosage', '') # Fallback
            )
            
        return Response({'status': 'Success', 'consultation_id': consultation.id})

    @action(detail=False, methods=['get'], url_path='treatment-history')
    def treatment_history(self, request):
        user = request.user
        if not hasattr(user, 'patient_profile'):
             return Response({'error': 'Patient profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        
        # Get consultations
        from .models import Consultation
        qs = Consultation.objects.filter(patient=user.patient_profile).order_by('-consultation_date')
        
        data = [{
            'id': c.id,
            'date': c.consultation_date.strftime('%d %b %Y, %I:%M %p') if c.consultation_date else '—',
            'doctor_name': c.doctor.get_full_name() if c.doctor else 'Doctor',
            'notes': c.chief_complaint or '',
            'diagnosis': c.diagnosis or '',
            'visit_type': c.visit_type or 'General',
            'blood_pressure': c.blood_pressure or '—',
            'temperature': c.temperature or '—',
            'weight': c.weight or '—'
        } for c in qs]
        
        return Response(data)


class ConsultationViewSet(viewsets.ModelViewSet):
    serializer_class = ConsultationSerializer
    queryset = Consultation.objects.all().order_by('-consultation_date')

    def get_queryset(self):
        user = self.request.user
        qs = Consultation.objects.all().order_by('-consultation_date')
        
        # Patients only see their own consultations
        if user.role == 'patient' and hasattr(user, 'patient_profile'):
            qs = qs.filter(patient=user.patient_profile)
        # Doctors see consultations they conducted
        elif user.role == 'doctor':
            qs = qs.filter(doctor=user)
        # Staff see consultations for their hospital
        elif user.hospital:
            qs = qs.filter(hospital=user.hospital)

        patient_uhid = self.request.query_params.get('patient')
        if patient_uhid:
            qs = qs.filter(patient__uhid=patient_uhid)
        return qs


class PrescriptionViewSet(viewsets.ModelViewSet):
    queryset = Prescription.objects.all()
    serializer_class = PrescriptionSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Prescription.objects.all().order_by('-prescribed_date')
        if user.role == 'patient' and hasattr(user, 'patient_profile'):
            qs = qs.filter(consultation__patient=user.patient_profile)
        elif user.role == 'doctor':
            qs = qs.filter(consultation__doctor=user)
        return qs


class PatientDocumentViewSet(viewsets.ModelViewSet):
    queryset = PatientDocument.objects.all()
    serializer_class = PatientDocumentSerializer

    def get_queryset(self):
        user = self.request.user
        qs = PatientDocument.objects.all().order_by('-upload_date')
        if user.role == 'patient' and hasattr(user, 'patient_profile'):
            qs = qs.filter(patient=user.patient_profile)
        return qs
