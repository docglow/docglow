with google as (
    select
        'google_ads' as channel,
        gs.campaign_id,
        gc.campaign_name,
        gs.date_day,
        gs.impressions,
        gs.clicks,
        gs.cost_usd as spend_usd,
        gs.conversions as leads
    from {{ ref('stg_google_ads__campaign_stats') }} gs
    left join {{ ref('stg_google_ads__campaigns') }} gc
        on gs.campaign_id = gc.campaign_id
),

facebook as (
    select
        'facebook_ads' as channel,
        fi.campaign_id,
        fc.campaign_name,
        fi.date_day,
        fi.impressions,
        fi.clicks,
        fi.spend_usd,
        fi.leads
    from {{ ref('stg_facebook_ads__ad_insights') }} fi
    left join {{ ref('stg_facebook_ads__campaigns') }} fc
        on fi.campaign_id = fc.campaign_id
)

select
    channel,
    campaign_id,
    campaign_name,
    date_day,
    impressions,
    clicks,
    spend_usd,
    leads
from google

union all

select
    channel,
    campaign_id,
    campaign_name,
    date_day,
    impressions,
    clicks,
    spend_usd,
    leads
from facebook
