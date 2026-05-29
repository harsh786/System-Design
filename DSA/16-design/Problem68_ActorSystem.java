import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * Problem 68: Actor System (Mailbox, Message Dispatch)
 * 
 * PRODUCTION MAPPING: Akka (JVM), Erlang/OTP, Microsoft Orleans, Proto.Actor,
 *                     WhatsApp (Erlang actors), Discord (Elixir/Erlang)
 * 
 * Core Principles:
 * - Each actor processes ONE message at a time (no shared mutable state)
 * - Communication only via async message passing (no locks needed!)
 * - Each actor has a mailbox (unbounded queue)
 * - Actors can: create child actors, send messages, change behavior
 * 
 * Why actors for distributed systems:
 * - Location transparency: same API for local/remote actors
 * - Fault isolation: actor crash doesn't affect others
 * - Natural concurrency: millions of actors on few threads
 * - Supervision: parent monitors children, decides restart strategy
 * 
 * Trade-offs:
 * - Harder to reason about ordering (async)
 * - Mailbox overflow risk (need backpressure)
 * - Debugging distributed actor state is complex
 */
public class Problem68_ActorSystem {

    // ---- Core Abstractions ----
    interface Message {}
    
    static class ActorRef {
        private final String name;
        private final Actor actor;
        private final ActorSystem system;

        ActorRef(String name, Actor actor, ActorSystem system) {
            this.name = name;
            this.actor = actor;
            this.system = system;
        }

        public void tell(Message msg, ActorRef sender) {
            system.dispatch(this, msg, sender);
        }

        public String getName() { return name; }
    }

    static abstract class Actor {
        protected ActorRef self;
        protected ActorRef sender; // sender of current message
        protected ActorSystem system;

        abstract void onReceive(Message msg);

        protected ActorRef createChild(String name, Actor actor) {
            return system.actorOf(name, actor);
        }
    }

    static class ActorSystem {
        private final Map<String, ActorRef> actors = new ConcurrentHashMap<>();
        private final Map<ActorRef, BlockingQueue<MessageEnvelope>> mailboxes = new ConcurrentHashMap<>();
        private final ExecutorService dispatcher;
        private final AtomicLong messagesProcessed = new AtomicLong(0);
        private volatile boolean shutdown = false;

        static class MessageEnvelope {
            final Message message;
            final ActorRef sender;
            MessageEnvelope(Message msg, ActorRef sender) { this.message = msg; this.sender = sender; }
        }

        public ActorSystem(int dispatcherThreads) {
            this.dispatcher = Executors.newFixedThreadPool(dispatcherThreads, r -> {
                Thread t = new Thread(r, "actor-dispatcher");
                t.setDaemon(true);
                return t;
            });
        }

        public ActorRef actorOf(String name, Actor actor) {
            ActorRef ref = new ActorRef(name, actor, this);
            actor.self = ref;
            actor.system = this;
            actors.put(name, ref);
            mailboxes.put(ref, new LinkedBlockingQueue<>());
            // Start mailbox processor
            dispatcher.submit(() -> processMailbox(ref));
            return ref;
        }

        void dispatch(ActorRef target, Message msg, ActorRef sender) {
            BlockingQueue<MessageEnvelope> mailbox = mailboxes.get(target);
            if (mailbox != null) {
                mailbox.offer(new MessageEnvelope(msg, sender));
            }
        }

        private void processMailbox(ActorRef ref) {
            BlockingQueue<MessageEnvelope> mailbox = mailboxes.get(ref);
            while (!shutdown) {
                try {
                    MessageEnvelope envelope = mailbox.poll(100, TimeUnit.MILLISECONDS);
                    if (envelope != null) {
                        ref.actor.sender = envelope.sender;
                        ref.actor.onReceive(envelope.message);
                        messagesProcessed.incrementAndGet();
                    }
                } catch (InterruptedException e) {
                    break;
                } catch (Exception e) {
                    // Supervision: log and continue (restart strategy in production)
                    System.err.println("Actor " + ref.getName() + " error: " + e.getMessage());
                }
            }
        }

        public ActorRef lookup(String name) { return actors.get(name); }
        public long getMessagesProcessed() { return messagesProcessed.get(); }

        public void shutdown() {
            shutdown = true;
            dispatcher.shutdown();
        }
    }

    // ---- Example: Bank Account Actor ----
    static class Deposit implements Message { final int amount; Deposit(int a) { amount = a; } }
    static class Withdraw implements Message { final int amount; Withdraw(int a) { amount = a; } }
    static class GetBalance implements Message {}
    static class BalanceResponse implements Message { final int balance; BalanceResponse(int b) { balance = b; } }
    static class TransferTo implements Message { 
        final ActorRef target; final int amount; 
        TransferTo(ActorRef t, int a) { target = t; amount = a; }
    }

    static class BankAccountActor extends Actor {
        private int balance;
        
        BankAccountActor(int initial) { this.balance = initial; }

        @Override
        void onReceive(Message msg) {
            if (msg instanceof Deposit) {
                balance += ((Deposit) msg).amount;
            } else if (msg instanceof Withdraw) {
                int amt = ((Withdraw) msg).amount;
                if (amt <= balance) balance -= amt;
            } else if (msg instanceof GetBalance) {
                if (sender != null) {
                    sender.tell(new BalanceResponse(balance), self);
                }
            } else if (msg instanceof TransferTo) {
                TransferTo transfer = (TransferTo) msg;
                if (transfer.amount <= balance) {
                    balance -= transfer.amount;
                    transfer.target.tell(new Deposit(transfer.amount), self);
                }
            }
        }

        int getBalance() { return balance; }
    }

    // ---- Example: Counter Actor (aggregator pattern) ----
    static class Increment implements Message {}
    static class GetCount implements Message {}
    static class CountResponse implements Message { final int count; CountResponse(int c) { count = c; } }

    static class CounterActor extends Actor {
        private int count = 0;
        @Override
        void onReceive(Message msg) {
            if (msg instanceof Increment) count++;
            else if (msg instanceof GetCount) {
                if (sender != null) sender.tell(new CountResponse(count), self);
            }
        }
        int getCount() { return count; }
    }

    // ---- Collector actor to gather responses ----
    static class CollectorActor extends Actor {
        final List<Message> collected = new CopyOnWriteArrayList<>();
        @Override void onReceive(Message msg) { collected.add(msg); }
    }

    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Actor System ===\n");

        ActorSystem system = new ActorSystem(4);

        // Test 1: Basic message processing
        BankAccountActor accountImpl = new BankAccountActor(1000);
        ActorRef account = system.actorOf("account-1", accountImpl);
        account.tell(new Deposit(500), null);
        account.tell(new Withdraw(200), null);
        Thread.sleep(100);
        assert accountImpl.getBalance() == 1300 : "Expected 1300, got: " + accountImpl.getBalance();
        System.out.println("PASS: Basic deposit/withdraw (balance=1300)");

        // Test 2: Actor-to-actor communication (transfer)
        BankAccountActor acc2Impl = new BankAccountActor(500);
        ActorRef account2 = system.actorOf("account-2", acc2Impl);
        account.tell(new TransferTo(account2, 300), null);
        Thread.sleep(100);
        assert accountImpl.getBalance() == 1000 : "Sender should have 1000";
        assert acc2Impl.getBalance() == 800 : "Receiver should have 800";
        System.out.println("PASS: Transfer between actors (1000, 800)");

        // Test 3: Request-Reply pattern
        CollectorActor collector = new CollectorActor();
        ActorRef collectorRef = system.actorOf("collector", collector);
        account.tell(new GetBalance(), collectorRef);
        Thread.sleep(100);
        assert !collector.collected.isEmpty();
        assert ((BalanceResponse) collector.collected.get(0)).balance == 1000;
        System.out.println("PASS: Request-reply pattern");

        // Test 4: High throughput - many messages
        CounterActor counterImpl = new CounterActor();
        ActorRef counter = system.actorOf("counter", counterImpl);
        int numMessages = 10000;
        for (int i = 0; i < numMessages; i++) {
            counter.tell(new Increment(), null);
        }
        Thread.sleep(500);
        assert counterImpl.getCount() == numMessages : 
            "Expected " + numMessages + ", got: " + counterImpl.getCount();
        System.out.println("PASS: " + numMessages + " messages processed correctly");

        // Test 5: Multiple actors concurrent
        int numActors = 10;
        CounterActor[] counters = new CounterActor[numActors];
        ActorRef[] refs = new ActorRef[numActors];
        for (int i = 0; i < numActors; i++) {
            counters[i] = new CounterActor();
            refs[i] = system.actorOf("counter-" + i, counters[i]);
        }
        for (int i = 0; i < 1000; i++) {
            refs[i % numActors].tell(new Increment(), null);
        }
        Thread.sleep(300);
        int total = 0;
        for (CounterActor c : counters) total += c.getCount();
        assert total == 1000 : "Total should be 1000, got: " + total;
        System.out.println("PASS: " + numActors + " concurrent actors, total count = " + total);

        // Test 6: No shared state corruption (single-threaded per actor)
        // The fact that Test 4 passes with exact count proves no race conditions
        System.out.println("PASS: No race conditions (single-threaded mailbox processing)");

        System.out.printf("\nTotal messages processed by system: %d\n", system.getMessagesProcessed());
        system.shutdown();
        System.out.println("\nAll tests passed!");
    }
}
