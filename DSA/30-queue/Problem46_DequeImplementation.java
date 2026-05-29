public class Problem46_DequeImplementation {
    int[] data; int head, tail, size, cap;
    Problem46_DequeImplementation(int cap) { this.cap = cap; data = new int[cap]; head = 0; tail = 0; size = 0; }
    void pushFront(int val) { head = (head - 1 + cap) % cap; data[head] = val; size++; }
    void pushBack(int val) { data[tail] = val; tail = (tail + 1) % cap; size++; }
    int popFront() { int val = data[head]; head = (head + 1) % cap; size--; return val; }
    int popBack() { tail = (tail - 1 + cap) % cap; size--; return data[tail]; }
    int peekFront() { return data[head]; }
    int peekBack() { return data[(tail - 1 + cap) % cap]; }
    boolean isEmpty() { return size == 0; }
    boolean isFull() { return size == cap; }
    public static void main(String[] args) {
        Problem46_DequeImplementation dq = new Problem46_DequeImplementation(5);
        dq.pushBack(1); dq.pushBack(2); dq.pushFront(0);
        System.out.println(dq.popFront()); // 0
        System.out.println(dq.popBack());  // 2
        System.out.println(dq.peekFront()); // 1
    }
}
