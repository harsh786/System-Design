public class Problem05_DesignLinkedList {
    static class Node { int val; Node prev, next; Node(int v){val=v;} }
    Node head = new Node(0), tail = new Node(0);
    int size = 0;
    
    Problem05_DesignLinkedList() { head.next = tail; tail.prev = head; }
    
    int get(int index) {
        if (index < 0 || index >= size) return -1;
        Node n = head.next; for (int i=0;i<index;i++) n=n.next; return n.val;
    }
    
    void addAtHead(int val) { addAfter(head, val); }
    void addAtTail(int val) { addAfter(tail.prev, val); }
    void addAtIndex(int index, int val) {
        if (index < 0 || index > size) return;
        Node n = head; for (int i=0;i<index;i++) n=n.next; addAfter(n, val);
    }
    void deleteAtIndex(int index) {
        if (index < 0 || index >= size) return;
        Node n = head.next; for (int i=0;i<index;i++) n=n.next;
        n.prev.next=n.next; n.next.prev=n.prev; size--;
    }
    void addAfter(Node node, int val) {
        Node n = new Node(val); n.next=node.next; n.prev=node;
        node.next.prev=n; node.next=n; size++;
    }
    
    public static void main(String[] args) {
        Problem05_DesignLinkedList l = new Problem05_DesignLinkedList();
        l.addAtHead(1); l.addAtTail(3); l.addAtIndex(1,2);
        System.out.println(l.get(1)); // 2
        l.deleteAtIndex(1);
        System.out.println(l.get(1)); // 3
    }
}
