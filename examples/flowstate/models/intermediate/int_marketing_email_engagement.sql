with events as (
    select
        email_campaign_id,
        event_type,
        contact_id
    from {{ ref('stg_hubspot__email_events') }}
),

campaigns as (
    select
        email_campaign_id,
        campaign_name,
        subject_line,
        email_type,
        send_date,
        num_recipients
    from {{ ref('stg_hubspot__email_campaigns') }}
)

select
    c.email_campaign_id,
    c.campaign_name,
    c.subject_line,
    c.email_type,
    c.send_date,
    c.num_recipients,
    count(case when e.event_type = 'open' then 1 end) as total_opens,
    count(case when e.event_type = 'click' then 1 end) as total_clicks,
    count(case when e.event_type = 'bounce' then 1 end) as total_bounces,
    count(case when e.event_type = 'unsubscribe' then 1 end) as total_unsubscribes,
    count(distinct case when e.event_type = 'open' then e.contact_id end) as unique_openers,
    count(distinct case when e.event_type = 'click' then e.contact_id end) as unique_clickers
from campaigns c
left join events e
    on c.email_campaign_id = e.email_campaign_id
group by 1, 2, 3, 4, 5, 6
