import React from 'react'
import type { LucideIcon } from 'lucide-react'

interface MetricCardProps {
  label: string
  value: string | number
  unit?: string
  trend?: string
  trendType?: 'blue' | 'red' | 'neutral'
  icon?: LucideIcon
  badgeText?: string
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  unit,
  trend,
  trendType = 'blue',
  icon: Icon,
  badgeText,
}) => {
  return (
    <div className="brutalist-card">
      <div className="brutalist-card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {Icon && <Icon size={14} color="var(--text-secondary)" />}
          <span className="mono-tag" style={{ color: 'var(--text-secondary)', fontWeight: 700 }}>
            {label}
          </span>
        </div>
        {badgeText && (
          <span className={`status-badge status-badge-${trendType}`}>
            {badgeText}
          </span>
        )}
      </div>

      <div className="brutalist-card-body" style={{ padding: '20px 18px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
          <span
            className="mono-metric"
            style={{
              fontSize: '36px',
              fontWeight: 800,
              color: 'var(--text-primary)',
              lineHeight: 1,
            }}
          >
            {value}
          </span>
          {unit && (
            <span
              className="mono-tag"
              style={{ fontSize: '14px', color: 'var(--text-secondary)' }}
            >
              {unit}
            </span>
          )}
        </div>

        {trend && (
          <div
            style={{
              marginTop: '12px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '12px',
              fontFamily: 'var(--font-mono)',
              color:
                trendType === 'red'
                  ? 'var(--red-hover)'
                  : trendType === 'blue'
                  ? 'var(--blue-electric)'
                  : 'var(--text-secondary)',
            }}
          >
            <span>{trend}</span>
          </div>
        )}
      </div>
    </div>
  )
}
