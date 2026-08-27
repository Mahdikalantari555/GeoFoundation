import { useQuery } from '@tanstack/react-query'
import { opsApi } from '@/api/ops'

export function useDoctor() {
  return useQuery({ queryKey: ['doctor'], queryFn: opsApi.doctor })
}

export function useDoctorLlm() {
  return useQuery({ queryKey: ['doctor', 'llm'], queryFn: opsApi.doctorLlm })
}
