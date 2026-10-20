Scene 1

AI agents are starting to spend real money.

They book things, buy things, pay for things.

That's useful… right up until a model gets talked into something.

If it can authorise a payment, one bad prompt can empty the wallet.


Scene 2

So we built Budget Kernel: a gate between the model and the money.

The model can only propose what it wants to pay, and to whom.

Then plain code decides.

Not another model.

And if the request says 'the owner said it's fine'?

That's never treated as permission.


Scene 3

Every request goes through the same checks.

Is the mandate still active?

Is it paying someone it's allowed to pay?

Is it within the limits?

Is there money left?

All of that happens in one database transaction.

If everything holds, the money's reserved.

If anything fails, it's refused, with a reason, and nothing moves.


Scene 4

Let's look at the real product.

A person creates an account.

Their password is hashed, and five wrong tries lock it.

Then they fund a mandate: a thousand dollars, with a hundred protected that can never be spent.

They create an agent… its key is shown once, and only once… and give it a narrower budget.

Three hundred dollars.

No more than a hundred a payment.

And anything over sixty, they want to be asked first.


Scene 5

Now the agent signs in with its own key, and just asks in plain words.

On the left is what the model proposed.

On the right, what the kernel decided.

Twenty dollars?

That's inside its budget.

Approved, and reserved.

A hundred and fifty?

Over the limit.

Refused, and it says why.


Scene 6

Eighty dollars is over that sixty-dollar line.

So the kernel holds it, and reserves nothing yet.

Only the owner can approve it… and when they do, every check runs again.


Scene 7

What if the agent keeps pushing?

After five refusals, it's suspended, automatically.

It can't undo that itself.

Only the owner can bring it back.


Scene 8

We also attack it on purpose.

The same attacks run against a deliberately unsafe version, and against the kernel, on a real database.

Here's one.

Eight payments arrive at the same moment, for a budget that only covers three.

The unsafe version approves all eight… two thousand four hundred dollars, out of a nine-hundred-dollar budget.

The kernel approves exactly three.

Across seven different attacks, it held every single time.


Scene 9

Every decision is written into a chained history, and the seal on the dashboard checks it.

Two payments the kernel approved really settled on Base Sepolia, a public testnet.

And the latest point in that history is anchored there too… so if anyone tries to rewrite the past, it shows.


Scene 10

To be clear about what this is: across every run we measured, zero unauthorised approvals.

But it's a testnet prototype.

It's not audited, it was tested on synthetic data, and it shouldn't hold real money.


Scene 11

Budget Kernel.

Models propose… the kernel decides.
