select
    date_trunc('month', gl.posted_at) as accounting_month,
    gl.account_id,
    acc.account_name,
    acc.account_type,
    acc.statement_category,
    sum(case when gl.debit_credit = 'debit' then gl.amount_usd else 0 end) as total_debits_usd,
    sum(case when gl.debit_credit = 'credit' then gl.amount_usd else 0 end) as total_credits_usd,
    sum(
        case
            when gl.debit_credit = 'credit' then gl.amount_usd
            else -gl.amount_usd
        end
    ) as net_amount_usd,
    count(gl.entry_id) as entry_count
from {{ ref('stg_quickbooks__general_ledger') }} gl
left join {{ ref('stg_quickbooks__accounts') }} acc on gl.account_id = acc.account_id
where acc.statement_category = 'profit_and_loss'
group by 1, 2, 3, 4, 5
