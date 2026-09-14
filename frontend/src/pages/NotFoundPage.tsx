import { ArrowLeft, Map } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button, Card, EmptyState } from '../components/ui'

export function NotFoundPage() {
  return (
    <div className="page page--centered">
      <Card><EmptyState icon={Map} title="This route is outside the network" description="The page may have moved, or the address was entered incorrectly." action={<Link to="/"><Button><ArrowLeft size={15} /> Back to dashboard</Button></Link>} /></Card>
    </div>
  )
}
