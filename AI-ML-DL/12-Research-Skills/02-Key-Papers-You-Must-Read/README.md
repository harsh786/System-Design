# Key Papers You Must Read

## Overview

This is a curated reading list of landmark ML papers organized by era and topic.
Each entry includes what the paper contributed, why it matters today, and where to find it.

**How to use this list**:
- Don't try to read everything at once. Pick 2-3 papers per week.
- Start with papers most relevant to your current work.
- Papers marked with ⭐ are the highest priority for a working ML engineer.
- Use the 3-pass method from Module 01.

---

## Foundations (1950s-2010)

These papers established the mathematical and algorithmic foundations of modern ML.

### The Perceptron
- **Title**: "The Perceptron: A Probabilistic Model for Information Storage and Organization in the Brain"
- **Authors**: Frank Rosenblatt
- **Year**: 1958
- **Venue**: Psychological Review
- **Key Contribution**: First trainable neural network model. Introduced the concept of learned weights updated by a simple learning rule.
- **Why It Matters**: Foundational concept. Every neural network today descends from this idea. Understanding its limitations (XOR problem) motivated multi-layer networks.
- **Link**: doi:10.1037/h0042519

### Backpropagation ⭐
- **Title**: "Learning Representations by Back-Propagating Errors"
- **Authors**: David Rumelhart, Geoffrey Hinton, Ronald Williams
- **Year**: 1986
- **Venue**: Nature
- **Key Contribution**: Efficient algorithm for computing gradients in multi-layer neural networks using the chain rule, enabling training of deep networks.
- **Why It Matters**: THE algorithm that makes deep learning possible. Still the foundation of all neural network training today.
- **Link**: doi:10.1038/323533a0

### Support Vector Machines
- **Title**: "The Nature of Statistical Learning Theory"
- **Authors**: Vladimir Vapnik
- **Year**: 1995
- **Venue**: Springer (Book)
- **Key Contribution**: Introduced SVMs with the kernel trick, maximum margin classification, and VC dimension theory for generalization bounds.
- **Why It Matters**: Dominated ML for a decade. Kernel methods remain relevant. VC theory provides fundamental understanding of generalization.
- **Link**: ISBN 978-0-387-98780-4

### Random Forests
- **Title**: "Random Forests"
- **Authors**: Leo Breiman
- **Year**: 2001
- **Venue**: Machine Learning Journal
- **Key Contribution**: Ensemble of decision trees with bagging and random feature selection. Demonstrated that combining many weak learners creates a strong learner.
- **Why It Matters**: Still a go-to algorithm for tabular data. Extremely robust, minimal tuning, handles mixed features. Basis for XGBoost/LightGBM intuitions.
- **Link**: doi:10.1023/A:1010933404324

### Word2Vec
- **Title**: "Efficient Estimation of Word Representations in Vector Space"
- **Authors**: Tomas Mikolov, Kai Chen, Greg Corrado, Jeffrey Dean
- **Year**: 2013
- **Venue**: ICLR Workshop
- **Key Contribution**: Efficient methods (Skip-gram, CBOW) for learning dense word embeddings from large corpora. Showed embeddings capture semantic relationships (king - man + woman ≈ queen).
- **Why It Matters**: Launched the embeddings revolution. Concept of learned dense representations now underlies all of modern NLP and recommendation systems.
- **Link**: arXiv:1301.3781

---

## Deep Learning Revolution (2012-2017)

The era when deep learning went from academic curiosity to dominant paradigm.

### AlexNet ⭐
- **Title**: "ImageNet Classification with Deep Convolutional Neural Networks"
- **Authors**: Alex Krizhevsky, Ilya Sutskever, Geoffrey Hinton
- **Year**: 2012
- **Venue**: NeurIPS
- **Key Contribution**: Won ImageNet 2012 by a massive margin using deep CNNs trained on GPUs. Used ReLU, dropout, data augmentation, and GPU training.
- **Why It Matters**: THE paper that started the deep learning revolution. Demonstrated that scale + GPUs + deep networks = breakthrough performance. Changed the entire field overnight.
- **Link**: Papers With Code: alexnet

### Dropout
- **Title**: "Dropout: A Simple Way to Prevent Neural Networks from Overfitting"
- **Authors**: Nitish Srivastava, Geoffrey Hinton, Alex Krizhevsky, Ilya Sutskever, Ruslan Salakhutdinov
- **Year**: 2014
- **Venue**: JMLR
- **Key Contribution**: Randomly dropping units during training prevents co-adaptation, acting as an efficient ensemble method and regularizer.
- **Why It Matters**: Simple, effective regularization that became standard in deep learning. Conceptually important: training-time noise as regularization.
- **Link**: jmlr.org/papers/v15/srivastava14a.html

### Generative Adversarial Networks ⭐
- **Title**: "Generative Adversarial Nets"
- **Authors**: Ian Goodfellow, Jean Pouget-Abadie, Mehdi Mirza, Bing Xu, David Warde-Farley, Sherjil Ozair, Aaron Courville, Yoshua Bengio
- **Year**: 2014
- **Venue**: NeurIPS
- **Key Contribution**: Two networks (generator and discriminator) trained adversarially. Generator learns to produce realistic samples by fooling the discriminator.
- **Why It Matters**: Opened the era of generative AI. Led to image synthesis, style transfer, data augmentation. Conceptually influenced many adversarial training approaches.
- **Link**: arXiv:1406.2661

### Adam Optimizer ⭐
- **Title**: "Adam: A Method for Stochastic Optimization"
- **Authors**: Diederik Kingma, Jimmy Ba
- **Year**: 2015
- **Venue**: ICLR
- **Key Contribution**: Adaptive learning rate optimizer combining momentum (first moment) and RMSProp (second moment) with bias correction.
- **Why It Matters**: Default optimizer for most deep learning. Understanding Adam (and its variants like AdamW) is essential for training any model.
- **Link**: arXiv:1412.6980

### Batch Normalization ⭐
- **Title**: "Batch Normalization: Accelerating Deep Network Training by Reducing Internal Covariate Shift"
- **Authors**: Sergey Ioffe, Christian Szegedy
- **Year**: 2015
- **Venue**: ICML
- **Key Contribution**: Normalizing layer inputs within mini-batches stabilizes training, allows higher learning rates, and acts as regularization.
- **Why It Matters**: Enabled training of much deeper networks reliably. Standard component in modern architectures. Spawned LayerNorm, GroupNorm, etc.
- **Link**: arXiv:1502.03167

### ResNet ⭐
- **Title**: "Deep Residual Learning for Image Recognition"
- **Authors**: Kaiming He, Xiangyu Zhang, Shaoqing Ren, Jian Sun
- **Year**: 2015
- **Venue**: CVPR 2016
- **Key Contribution**: Skip connections (residual connections) enable training of extremely deep networks (100+ layers) by allowing gradient flow through identity mappings.
- **Why It Matters**: Residual connections are now EVERYWHERE - transformers, diffusion models, any deep architecture. Solved the degradation problem.
- **Link**: arXiv:1512.03385

### Seq2Seq with Attention
- **Title**: "Neural Machine Translation by Jointly Learning to Align and Translate"
- **Authors**: Dzmitry Bahdanau, Kyunghyun Cho, Yoshua Bengio
- **Year**: 2015
- **Venue**: ICLR
- **Key Contribution**: Attention mechanism allowing decoder to focus on relevant parts of input sequence, rather than compressing everything into fixed-length vector.
- **Why It Matters**: Introduced attention to NLP. Direct ancestor of the Transformer. Attention is now the core primitive of modern deep learning.
- **Link**: arXiv:1409.0473

---

## Transformer Era (2017-2020)

The architecture that would come to dominate all of AI.

### Attention Is All You Need ⭐
- **Title**: "Attention Is All You Need"
- **Authors**: Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan Gomez, Łukasz Kaiser, Illia Polosukhin
- **Year**: 2017
- **Venue**: NeurIPS
- **Key Contribution**: The Transformer architecture - replacing recurrence entirely with multi-head self-attention. Introduced Q/K/V formulation, positional encodings, and the encoder-decoder structure.
- **Why It Matters**: Foundation of ALL modern LLMs, vision transformers, and multimodal models. The single most influential architecture paper of the decade.
- **Link**: arXiv:1706.03762

### BERT ⭐
- **Title**: "BERT: Pre-Training of Deep Bidirectional Transformers for Language Understanding"
- **Authors**: Jacob Devlin, Ming-Wei Chang, Kenton Lee, Kristina Toutanova
- **Year**: 2018
- **Venue**: NAACL 2019
- **Key Contribution**: Pre-training a bidirectional Transformer with masked language modeling and next sentence prediction, then fine-tuning on downstream tasks.
- **Why It Matters**: Established the pre-train/fine-tune paradigm. Showed massive gains from unsupervised pre-training. Still widely used for classification, NER, search.
- **Link**: arXiv:1810.04805

### GPT-2
- **Title**: "Language Models are Unsupervised Multitask Learners"
- **Authors**: Alec Radford, Jeffrey Wu, Rewon Child, David Luan, Dario Amodei, Ilya Sutskever
- **Year**: 2019
- **Venue**: OpenAI Technical Report
- **Key Contribution**: Showed that scaling up autoregressive language models (1.5B params) leads to emergent zero-shot capabilities across many tasks without fine-tuning.
- **Why It Matters**: Demonstrated the scaling hypothesis - bigger models learn more general capabilities. Direct precursor to GPT-3/4 and the LLM paradigm.
- **Link**: OpenAI blog / GitHub

### T5
- **Title**: "Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer"
- **Authors**: Colin Raffel, Noam Shazeer, Adam Roberts, Katherine Lee, Sharan Narang, Michael Matena, Yanqi Zhou, Wei Li, Peter J. Liu
- **Year**: 2019
- **Venue**: JMLR 2020
- **Key Contribution**: Unified all NLP tasks as text-to-text. Systematic study of pre-training objectives, architectures, datasets, and scale.
- **Why It Matters**: Most comprehensive study of transfer learning design decisions. Text-to-text framing influenced instruction tuning and prompt engineering.
- **Link**: arXiv:1910.10683

---

## LLM Era (2020-Present)

The era of massive language models and their applications.

### GPT-3 ⭐
- **Title**: "Language Models are Few-Shot Learners"
- **Authors**: Tom Brown, Benjamin Mann, Nick Ryder, Melanie Subbiah, et al.
- **Year**: 2020
- **Venue**: NeurIPS
- **Key Contribution**: 175B parameter model demonstrating that large LMs can perform tasks via in-context learning (few-shot prompting) without gradient updates.
- **Why It Matters**: Launched the era of prompt engineering and in-context learning. Showed emergent abilities at scale. Foundation for ChatGPT.
- **Link**: arXiv:2005.14165

### RAG (Retrieval-Augmented Generation) ⭐
- **Title**: "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"
- **Authors**: Patrick Lewis, Ethan Perez, Aleksandra Piktus, Fabio Petroni, Vladimir Karpukhin, Naman Goyal, Heinrich Küttler, Mike Lewis, Wen-tau Yih, Tim Rocktäschel, Sebastian Riedel, Douwe Kiela
- **Year**: 2020
- **Venue**: NeurIPS
- **Key Contribution**: Combining a pre-trained retriever (DPR) with a pre-trained generator (BART) to ground generation in retrieved documents.
- **Why It Matters**: THE architecture pattern for enterprise LLM applications. Reduces hallucination, enables knowledge updates without retraining.
- **Link**: arXiv:2005.11401

### LoRA ⭐
- **Title**: "LoRA: Low-Rank Adaptation of Large Language Models"
- **Authors**: Edward Hu, Yelong Shen, Phillip Wallis, Zeyuan Allen-Zhu, Yuanzhi Li, Shean Wang, Lu Wang, Weizhu Chen
- **Year**: 2021
- **Venue**: ICLR 2022
- **Key Contribution**: Efficient fine-tuning by freezing pre-trained weights and injecting trainable low-rank decomposition matrices into transformer layers.
- **Why It Matters**: Made fine-tuning LLMs practical for everyone. Orders of magnitude less memory and compute than full fine-tuning. Standard technique today.
- **Link**: arXiv:2106.09685

### InstructGPT / RLHF ⭐
- **Title**: "Training language models to follow instructions with human feedback"
- **Authors**: Long Ouyang, Jeff Wu, Xu Jiang, Diogo Almeida, et al.
- **Year**: 2022
- **Venue**: NeurIPS
- **Key Contribution**: Three-step process: supervised fine-tuning on demonstrations, training a reward model from human preferences, and optimizing the policy with PPO (RLHF).
- **Why It Matters**: THE technique that made ChatGPT possible. Aligns LLMs with human intent. RLHF is now standard for all production LLMs.
- **Link**: arXiv:2203.02155

### Chain-of-Thought Prompting ⭐
- **Title**: "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models"
- **Authors**: Jason Wei, Xuezhi Wang, Dale Schuurmans, Maarten Bosma, Brian Ichter, Fei Xia, Ed Chi, Quoc Le, Denny Zhou
- **Year**: 2022
- **Venue**: NeurIPS
- **Key Contribution**: Adding "let's think step by step" reasoning examples in prompts dramatically improves LLM performance on math, logic, and commonsense reasoning.
- **Why It Matters**: Simple technique with massive impact. Showed LLMs can reason better when prompted to show work. Foundation for reasoning agents.
- **Link**: arXiv:2201.11903

### Constitutional AI
- **Title**: "Constitutional AI: Harmlessness from AI Feedback"
- **Authors**: Yuntao Bai, Saurav Kadavath, Sandipan Kundu, et al.
- **Year**: 2022
- **Venue**: Anthropic Technical Report
- **Key Contribution**: Training AI to be helpful and harmless using a set of principles (constitution) and AI-generated feedback (RLAIF) rather than extensive human labeling.
- **Why It Matters**: Scalable alignment approach. Reduces need for human preference data. Influences how safety is built into models.
- **Link**: arXiv:2212.08073

### Flash Attention ⭐
- **Title**: "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness"
- **Authors**: Tri Dao, Daniel Fu, Stefano Ermon, Atri Rudra, Christopher Ré
- **Year**: 2022
- **Venue**: NeurIPS
- **Key Contribution**: IO-aware implementation of exact attention that reduces memory from O(N²) to O(N) and is 2-4x faster by minimizing HBM reads/writes through tiling.
- **Why It Matters**: Enables training with much longer sequences. Now standard in all LLM training. Shows that systems-level thinking can unlock algorithmic improvements.
- **Link**: arXiv:2205.14135

### Mixture of Experts
- **Title**: "Outrageously Large Neural Networks: The Sparsely-Gated Mixture-of-Experts Layer"
- **Authors**: Noam Shazeer, Azalia Mirhoseini, Krzysztof Maziarz, Andy Davis, Quoc Le, Geoffrey Hinton, Jeff Dean
- **Year**: 2017 (concept), applied extensively 2022+
- **Venue**: ICLR
- **Key Contribution**: Conditional computation where only a subset of "expert" sub-networks are activated per input, allowing massive model capacity with manageable compute.
- **Why It Matters**: Architecture behind Mixtral, likely GPT-4, and other frontier models. Enables scaling parameters without proportionally scaling compute.
- **Link**: arXiv:1701.06538

### DPO (Direct Preference Optimization)
- **Title**: "Direct Preference Optimization: Your Language Model is Secretly a Reward Model"
- **Authors**: Rafael Rafailov, Archit Sharma, Eric Mitchell, Stefano Ermon, Christopher Manning, Chelsea Finn
- **Year**: 2023
- **Venue**: NeurIPS
- **Key Contribution**: Eliminates the need for a separate reward model in RLHF by directly optimizing the policy from preference data using a simple classification loss.
- **Why It Matters**: Simpler, more stable alternative to PPO-based RLHF. Widely adopted for alignment. Easier to implement and tune.
- **Link**: arXiv:2305.18290

---

## Vision

### Vision Transformer (ViT) ⭐
- **Title**: "An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale"
- **Authors**: Alexey Dosovitskiy, Lucas Beyer, Alexander Kolesnikov, et al.
- **Year**: 2020
- **Venue**: ICLR 2021
- **Key Contribution**: Applied standard Transformer directly to image patches (16x16), achieving SOTA on image classification with sufficient pre-training data.
- **Why It Matters**: Proved Transformers can replace CNNs for vision. Unified architecture across modalities. Enabled multimodal models.
- **Link**: arXiv:2010.11929

### CLIP ⭐
- **Title**: "Learning Transferable Visual Models From Natural Language Supervision"
- **Authors**: Alec Radford, Jong Wook Kim, Chris Hallacy, et al.
- **Year**: 2021
- **Venue**: ICML
- **Key Contribution**: Contrastive pre-training on 400M image-text pairs. Learns visual representations aligned with language, enabling zero-shot image classification.
- **Why It Matters**: Bridge between vision and language. Enables zero-shot visual understanding. Foundation for DALL-E, Stable Diffusion, and multimodal AI.
- **Link**: arXiv:2103.00020

### Denoising Diffusion Probabilistic Models (DDPM)
- **Title**: "Denoising Diffusion Probabilistic Models"
- **Authors**: Jonathan Ho, Ajay Jain, Pieter Abbeel
- **Year**: 2020
- **Venue**: NeurIPS
- **Key Contribution**: Showed diffusion models (gradually denoising from noise to data) can generate high-quality images, rivaling GANs with more stable training.
- **Why It Matters**: Foundation of Stable Diffusion, DALL-E 2, Midjourney. Diffusion models now dominate image/video/audio generation.
- **Link**: arXiv:2006.11239

### Stable Diffusion / Latent Diffusion
- **Title**: "High-Resolution Image Synthesis with Latent Diffusion Models"
- **Authors**: Robin Rombach, Andreas Blattmann, Dominik Lorenz, Patrick Esser, Björn Ommer
- **Year**: 2022
- **Venue**: CVPR
- **Key Contribution**: Running diffusion in a compressed latent space (via autoencoder) rather than pixel space, making high-resolution generation computationally feasible.
- **Why It Matters**: Made image generation practical and accessible. Open-source release democratized generative AI.
- **Link**: arXiv:2112.10752

---

## Recommendation Systems / Industry

### Wide & Deep Learning
- **Title**: "Wide & Deep Learning for Recommender Systems"
- **Authors**: Heng-Tze Cheng, Levent Koc, Jeremiah Harmsen, et al. (Google)
- **Year**: 2016
- **Venue**: DLRS Workshop @ RecSys
- **Key Contribution**: Combining a wide linear model (memorization of feature interactions) with a deep neural network (generalization) for app recommendations.
- **Why It Matters**: Influential industry architecture. Showed how to combine traditional feature engineering with deep learning. Template for many production systems.
- **Link**: arXiv:1606.07792

### Deep Learning Recommendation Model (DLRM)
- **Title**: "Deep Learning Recommendation Model for Personalization and Recommendation Systems"
- **Authors**: Maxim Naumov, Dheevatsa Mudigere, et al. (Facebook)
- **Year**: 2019
- **Venue**: arXiv
- **Key Contribution**: Reference architecture for production recommendation: embedding tables for sparse features, MLP for dense features, feature interaction layer, and top MLP for prediction.
- **Why It Matters**: De facto industry standard architecture for large-scale recommendations. Drives much of Meta's ad and content ranking.
- **Link**: arXiv:1906.00091

### Scaling Laws for Neural Language Models
- **Title**: "Scaling Laws for Neural Language Models"
- **Authors**: Jared Kaplan, Sam McCandlish, Tom Henighan, et al.
- **Year**: 2020
- **Venue**: arXiv (OpenAI)
- **Key Contribution**: Power-law relationships between model performance and compute, dataset size, and parameter count. Larger models are more sample-efficient.
- **Why It Matters**: Provides principled framework for deciding how to allocate compute budget. Explains why scaling works and predicts returns from investment.
- **Link**: arXiv:2001.08361

### Chinchilla (Training Compute-Optimal LLMs)
- **Title**: "Training Compute-Optimal Large Language Models"
- **Authors**: Jordan Hoffmann, Sebastian Borgeaud, Arthur Mensch, et al. (DeepMind)
- **Year**: 2022
- **Venue**: NeurIPS
- **Key Contribution**: For a fixed compute budget, model size and training data should be scaled equally. Previous models (like GPT-3) were significantly undertrained.
- **Why It Matters**: Changed how the industry trains LLMs. Led to smaller but better-trained models. Influenced LLaMA and subsequent open models.
- **Link**: arXiv:2203.15556

---

## Reading Order Recommendation

### If you're new to ML (start here):
1. Backpropagation (Rumelhart, 1986)
2. AlexNet (2012)
3. Adam (2015)
4. Batch Normalization (2015)
5. ResNet (2015)
6. Attention Is All You Need (2017)
7. BERT (2018)
8. GPT-3 (2020)

### If you're building LLM applications:
1. Attention Is All You Need (2017)
2. GPT-3 (2020)
3. RAG (2020)
4. InstructGPT/RLHF (2022)
5. Chain-of-Thought (2022)
6. LoRA (2021)
7. Flash Attention (2022)
8. DPO (2023)

### If you're in computer vision:
1. AlexNet (2012)
2. ResNet (2015)
3. ViT (2020)
4. CLIP (2021)
5. DDPM (2020)
6. Latent Diffusion (2022)

### If you're building recommendation systems:
1. Word2Vec (2013)
2. Wide & Deep (2016)
3. DLRM (2019)
4. Scaling Laws (2020)
5. Attention Is All You Need (2017)

---

## Tracking New Papers

After building your foundation with the papers above, stay current:

1. **Papers With Code** - Track SOTA across benchmarks
2. **arXiv Sanity** - Personalized paper recommendations
3. **Semantic Scholar** - Citation alerts for papers you care about
4. **Conference best paper awards** - Highest signal, annual
5. **ML Twitter/X** - Real-time discussion and hot takes

---

## Summary

This list is opinionated and focused on papers that shaped how we build ML systems today.
The field moves fast - papers from this year may belong on this list next year. Use this
as a starting point, not a complete canon.
