import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;
import java.util.stream.*;

public class Problem50_ActorModelMessagePassing {
    /**
     * Problem: Actor Model Message Passing
     * Simple actor system with mailbox and message processing.
     * Time: O(1) send, O(messages) process | Space: O(mailbox)
     * Production Analogy: Akka actors, Erlang processes - isolated state, message-driven.
     */
    interface Message {}
    static class Increment implements Message { final int amount; Increment(int a) { amount = a; } }
    static class GetValue implements Message { final CompletableFuture<Integer> reply; GetValue(CompletableFuture<Integer> r) { reply = r; } }

    static class Actor {
        private final BlockingQueue<Message> mailbox = new LinkedBlockingQueue<>();
        private int state = 0;

        public void start() {
            new Thread(() -> {
                while (true) {
                    try {
                        Message msg = mailbox.take();
                        if (msg instanceof Increment) state += ((Increment) msg).amount;
                        else if (msg instanceof GetValue) ((GetValue) msg).reply.complete(state);
                    } catch (InterruptedException e) { break; }
                }
            }).start();
        }

        public void send(Message msg) { mailbox.add(msg); }
    }

    public static void main(String[] args) throws Exception {
        Actor counter = new Actor();
        counter.start();
        counter.send(new Increment(5));
        counter.send(new Increment(3));
        counter.send(new Increment(2));
        Thread.sleep(100);
        CompletableFuture<Integer> future = new CompletableFuture<>();
        counter.send(new GetValue(future));
        System.out.println("Actor state: " + future.get() + " (expected 10)");
        System.exit(0);
    }
}
