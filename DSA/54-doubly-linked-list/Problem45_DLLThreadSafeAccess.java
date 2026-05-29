import java.util.*;
import java.util.concurrent.locks.ReentrantReadWriteLock;

public class Problem45_DLLThreadSafeAccess {
    static class Node{int val;Node prev,next;Node(int v){val=v;}}
    Node head=new Node(0),tail=new Node(0);
    ReentrantReadWriteLock lock=new ReentrantReadWriteLock();
    
    Problem45_DLLThreadSafeAccess(){head.next=tail;tail.prev=head;}
    
    void add(int val){
        lock.writeLock().lock();
        try{Node n=new Node(val);n.prev=tail.prev;n.next=tail;tail.prev.next=n;tail.prev=n;}
        finally{lock.writeLock().unlock();}
    }
    
    List<Integer> snapshot(){
        lock.readLock().lock();
        try{List<Integer> r=new ArrayList<>();Node c=head.next;while(c!=tail){r.add(c.val);c=c.next;}return r;}
        finally{lock.readLock().unlock();}
    }
    
    public static void main(String[] args) throws Exception {
        Problem45_DLLThreadSafeAccess dll=new Problem45_DLLThreadSafeAccess();
        Thread t1=new Thread(()->{for(int i=0;i<5;i++)dll.add(i);});
        Thread t2=new Thread(()->{for(int i=5;i<10;i++)dll.add(i);});
        t1.start();t2.start();t1.join();t2.join();
        System.out.println("Size: "+dll.snapshot().size()); // 10
    }
}
