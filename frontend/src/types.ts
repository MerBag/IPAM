export type Id = number | string

export type User = {
  id: Id
  username: string
  full_name?: string
  email?: string
  role?: 'admin' | 'operator' | 'read_only' | string
  is_active?: boolean
  last_login_at?: string | null
  created_at?: string
}

export type Prefix = {
  id: Id
  cidr: string
  network_address?: string
  broadcast_address?: string
  prefix_length?: number
  name?: string
  description?: string
  location?: string
  first_usable_ip?: string
  last_usable_ip?: string
  total_addresses?: number
  used_addresses?: number
  free_addresses?: number
  utilization?: number
  utilization_percent?: number
  created_at?: string
}

export type Subnet = {
  id?: Id
  prefix_id?: Id
  parent_id?: Id | null
  parent_subnet_id?: Id | null
  cidr: string
  network_address?: string
  broadcast_address?: string
  prefix_length?: number
  name?: string
  status?: string
  total_addresses?: number
  used_addresses?: number
  free_addresses?: number
  utilization?: number
  utilization_percent?: number
  first_usable_ip?: string
  last_usable_ip?: string
  gateway?: string
}

export type IpStatus =
  | 'free'
  | 'assigned'
  | 'reserved'
  | 'gateway'
  | 'network'
  | 'broadcast'
  | 'blackholed'
  | string

export type IpAddress = {
  id: Id
  address: string
  ip_address?: string
  subnet_id?: Id
  subnet?: Subnet
  status: IpStatus
  reserved_by_subnet?: boolean
  hostname?: string
  device_id?: Id | null
  device_name?: string
  device?: { id: Id; name: string }
  customer_id?: Id | null
  customer_name?: string
  customer?: { id: Id; name: string }
  purpose?: string
  location?: string
  router_id?: Id | null
  router_name?: string
  router?: { id: Id; name: string }
  interface?: string
  vlan?: string | number
  mac_address?: string
  notes?: string
  reverse_dns?: string
  assigned_at?: string
  date_assigned?: string
  updated_at?: string
  assigned_by?: string | { username?: string; full_name?: string }
}

export type DashboardStats = {
  total_ips?: number
  used_ips?: number
  assigned_ips?: number
  free_ips?: number
  reserved_ips?: number
  utilization?: number
  utilization_percent?: number
  subnet_count?: number
  subnets?: number
  device_count?: number
  devices?: number
  recent_assignments?: Allocation[]
  prefixes?: Prefix[]
}

export type Allocation = {
  id: Id
  ip_address_id: Id
  subnet_id?: Id | null
  action: string
  previous_status?: string | null
  new_status: string
  snapshot?: Record<string, unknown>
  actor_id?: Id | null
  created_at: string
}

export type Device = {
  id: Id
  name: string
  type?: string
  management_ip?: string
  mac_address?: string
  location?: string
  description?: string
  ip_count?: number
  updated_at?: string
}

export type Customer = {
  id: Id
  name: string
  reference?: string
  account_reference?: string
  contact_name?: string
  email?: string
  phone?: string
  notes?: string
  ip_count?: number
  updated_at?: string
}

export type Router = {
  id: Id
  name: string
  management_ip?: string
  platform?: string
  api_port?: number
  username?: string
  enabled?: boolean
  location?: string
  description?: string
  notes?: string
  status?: string
  last_seen_at?: string
  ip_count?: number
  updated_at?: string
}

export type AuditLog = {
  id: Id
  action: string
  entity_type?: string
  entity_id?: Id
  description?: string
  details?: Record<string, unknown>
  actor_id?: Id | null
  user?: User | string
  username?: string
  ip_address?: string
  source_ip?: string
  created_at: string
  metadata?: Record<string, unknown>
}

export type SearchResult = {
  id: Id
  type?: string
  entity_type?: string
  primary?: string
  secondary?: string
  title?: string
  label?: string
  subtitle?: string
  value?: string
  address?: string
  cidr?: string
}

export type Paginated<T> = {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}
