import java.util.*;

/**
 * Iterator Design Pattern - Complete Implementation
 * Provides a way to access elements of a collection sequentially
 * without exposing its underlying representation.
 */
public class IteratorPattern {

    // ==================== CORE INTERFACES ====================

    interface Iterator<T> {
        boolean hasNext();
        T next();
        void reset();
    }

    interface IterableCollection<T> {
        Iterator<T> createIterator();
    }

    // ==================== EXAMPLE 1: Notification Collection (Array-based) ====================

    static class Notification {
        String message;
        String type;

        Notification(String message, String type) {
            this.message = message;
            this.type = type;
        }

        @Override
        public String toString() {
            return "[" + type + "] " + message;
        }
    }

    static class NotificationIterator implements Iterator<Notification> {
        private Notification[] notifications;
        private int position = 0;
        private int count;

        NotificationIterator(Notification[] notifications, int count) {
            this.notifications = notifications;
            this.count = count;
        }

        @Override
        public boolean hasNext() {
            return position < count && notifications[position] != null;
        }

        @Override
        public Notification next() {
            if (!hasNext()) throw new NoSuchElementException();
            return notifications[position++];
        }

        @Override
        public void reset() {
            position = 0;
        }
    }

    static class NotificationCollection implements IterableCollection<Notification> {
        private Notification[] notifications;
        private int count = 0;
        private static final int MAX = 10;

        NotificationCollection() {
            notifications = new Notification[MAX];
        }

        void addNotification(String message, String type) {
            if (count < MAX) {
                notifications[count++] = new Notification(message, type);
            }
        }

        @Override
        public Iterator<Notification> createIterator() {
            return new NotificationIterator(notifications, count);
        }
    }

    // ==================== EXAMPLE 2: Custom LinkedList with Forward/Reverse Iterators ====================

    static class Node<T> {
        T data;
        Node<T> next;
        Node<T> prev;

        Node(T data) {
            this.data = data;
        }
    }

    static class DoublyLinkedList<T> implements IterableCollection<T> {
        Node<T> head;
        Node<T> tail;
        int size = 0;

        void add(T data) {
            Node<T> node = new Node<>(data);
            if (head == null) {
                head = tail = node;
            } else {
                tail.next = node;
                node.prev = tail;
                tail = node;
            }
            size++;
        }

        @Override
        public Iterator<T> createIterator() {
            return new ForwardIterator();
        }

        public Iterator<T> createReverseIterator() {
            return new ReverseIterator();
        }

        class ForwardIterator implements Iterator<T> {
            Node<T> current = head;

            @Override
            public boolean hasNext() { return current != null; }

            @Override
            public T next() {
                if (!hasNext()) throw new NoSuchElementException();
                T data = current.data;
                current = current.next;
                return data;
            }

            @Override
            public void reset() { current = head; }
        }

        class ReverseIterator implements Iterator<T> {
            Node<T> current = tail;

            @Override
            public boolean hasNext() { return current != null; }

            @Override
            public T next() {
                if (!hasNext()) throw new NoSuchElementException();
                T data = current.data;
                current = current.prev;
                return data;
            }

            @Override
            public void reset() { current = tail; }
        }
    }

    // ==================== EXAMPLE 3: Social Network Graph with BFS/DFS Iterators ====================

    static class Person {
        String name;
        List<Person> friends = new ArrayList<>();

        Person(String name) { this.name = name; }

        void addFriend(Person p) {
            if (!friends.contains(p)) {
                friends.add(p);
                p.friends.add(this);
            }
        }

        @Override
        public String toString() { return name; }
    }

    static class SocialNetwork implements IterableCollection<Person> {
        private Person root;

        SocialNetwork(Person root) { this.root = root; }

        @Override
        public Iterator<Person> createIterator() {
            return new BFSIterator(root);
        }

        public Iterator<Person> createDFSIterator() {
            return new DFSIterator(root);
        }
    }

    static class BFSIterator implements Iterator<Person> {
        private Queue<Person> queue = new LinkedList<>();
        private Set<Person> visited = new LinkedHashSet<>();
        private Person root;

        BFSIterator(Person start) {
            this.root = start;
            queue.add(start);
            visited.add(start);
        }

        @Override
        public boolean hasNext() { return !queue.isEmpty(); }

        @Override
        public Person next() {
            if (!hasNext()) throw new NoSuchElementException();
            Person current = queue.poll();
            for (Person friend : current.friends) {
                if (!visited.contains(friend)) {
                    visited.add(friend);
                    queue.add(friend);
                }
            }
            return current;
        }

        @Override
        public void reset() {
            queue.clear();
            visited.clear();
            queue.add(root);
            visited.add(root);
        }
    }

    static class DFSIterator implements Iterator<Person> {
        private Deque<Person> stack = new ArrayDeque<>();
        private Set<Person> visited = new LinkedHashSet<>();
        private Person root;

        DFSIterator(Person start) {
            this.root = start;
            stack.push(start);
        }

        @Override
        public boolean hasNext() { return !stack.isEmpty(); }

        @Override
        public Person next() {
            if (!hasNext()) throw new NoSuchElementException();
            Person current;
            while (true) {
                current = stack.pop();
                if (!visited.contains(current)) break;
                if (stack.isEmpty()) throw new NoSuchElementException();
            }
            visited.add(current);
            List<Person> friends = current.friends;
            for (int i = friends.size() - 1; i >= 0; i--) {
                if (!visited.contains(friends.get(i))) {
                    stack.push(friends.get(i));
                }
            }
            return current;
        }

        @Override
        public void reset() {
            stack.clear();
            visited.clear();
            stack.push(root);
        }
    }

    // ==================== INTERNAL vs EXTERNAL ITERATION ====================

    // Internal iterator - collection controls the iteration
    interface InternalIterator<T> {
        void forEach(java.util.function.Consumer<T> action);
        void forEachFiltered(java.util.function.Predicate<T> filter, java.util.function.Consumer<T> action);
    }

    static class NumberCollection implements InternalIterator<Integer>, IterableCollection<Integer> {
        private List<Integer> numbers = new ArrayList<>();

        void add(Integer n) { numbers.add(n); }

        // Internal iteration - collection controls traversal
        @Override
        public void forEach(java.util.function.Consumer<Integer> action) {
            for (Integer n : numbers) action.accept(n);
        }

        @Override
        public void forEachFiltered(java.util.function.Predicate<Integer> filter,
                                     java.util.function.Consumer<Integer> action) {
            for (Integer n : numbers) {
                if (filter.test(n)) action.accept(n);
            }
        }

        // External iteration - client controls traversal
        @Override
        public Iterator<Integer> createIterator() {
            return new Iterator<Integer>() {
                int idx = 0;

                @Override
                public boolean hasNext() { return idx < numbers.size(); }

                @Override
                public Integer next() {
                    if (!hasNext()) throw new NoSuchElementException();
                    return numbers.get(idx++);
                }

                @Override
                public void reset() { idx = 0; }
            };
        }
    }

    // ==================== MAIN ====================

    public static void main(String[] args) {
        System.out.println("=== ITERATOR DESIGN PATTERN ===\n");

        // Example 1: Notification Collection
        System.out.println("--- Example 1: Notification Collection (Array-based) ---");
        NotificationCollection nc = new NotificationCollection();
        nc.addNotification("You have a new message", "MSG");
        nc.addNotification("Your order shipped", "ORDER");
        nc.addNotification("Payment received", "PAYMENT");
        nc.addNotification("Friend request from Alice", "SOCIAL");

        Iterator<Notification> nIter = nc.createIterator();
        while (nIter.hasNext()) {
            System.out.println("  " + nIter.next());
        }
        System.out.println("  [Reset and iterate again]");
        nIter.reset();
        System.out.println("  First after reset: " + nIter.next());

        // Example 2: Doubly Linked List
        System.out.println("\n--- Example 2: DoublyLinkedList with Forward/Reverse ---");
        DoublyLinkedList<String> list = new DoublyLinkedList<>();
        list.add("Alpha");
        list.add("Beta");
        list.add("Gamma");
        list.add("Delta");

        System.out.print("  Forward:  ");
        Iterator<String> fwd = list.createIterator();
        while (fwd.hasNext()) System.out.print(fwd.next() + " -> ");
        System.out.println("END");

        System.out.print("  Reverse:  ");
        Iterator<String> rev = list.createReverseIterator();
        while (rev.hasNext()) System.out.print(rev.next() + " -> ");
        System.out.println("END");

        // Example 3: Social Network BFS/DFS
        System.out.println("\n--- Example 3: Social Network Traversal ---");
        Person alice = new Person("Alice");
        Person bob = new Person("Bob");
        Person charlie = new Person("Charlie");
        Person diana = new Person("Diana");
        Person eve = new Person("Eve");
        Person frank = new Person("Frank");

        alice.addFriend(bob);
        alice.addFriend(charlie);
        bob.addFriend(diana);
        bob.addFriend(eve);
        charlie.addFriend(frank);

        //    Alice -- Bob -- Diana
        //      |       |
        //    Charlie  Eve
        //      |
        //    Frank

        SocialNetwork network = new SocialNetwork(alice);

        System.out.print("  BFS: ");
        Iterator<Person> bfs = network.createIterator();
        while (bfs.hasNext()) System.out.print(bfs.next() + " ");
        System.out.println();

        System.out.print("  DFS: ");
        Iterator<Person> dfs = network.createDFSIterator();
        while (dfs.hasNext()) System.out.print(dfs.next() + " ");
        System.out.println();

        // Example 4: Internal vs External Iteration
        System.out.println("\n--- Example 4: Internal vs External Iteration ---");
        NumberCollection nums = new NumberCollection();
        for (int i = 1; i <= 10; i++) nums.add(i);

        System.out.print("  External (client controls): ");
        Iterator<Integer> extIter = nums.createIterator();
        while (extIter.hasNext()) {
            int val = extIter.next();
            if (val % 2 == 0) System.out.print(val + " ");
        }
        System.out.println();

        System.out.print("  Internal (collection controls): ");
        nums.forEachFiltered(n -> n % 2 == 0, n -> System.out.print(n + " "));
        System.out.println();

        System.out.print("  Internal (all elements): ");
        nums.forEach(n -> System.out.print(n + " "));
        System.out.println();

        System.out.println("\n=== Key Takeaway: Client iterates without knowing if it's an array, linked list, or graph! ===");
    }
}
