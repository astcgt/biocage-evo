# V05 (r0002): does FEBio keep a stick point across load increments? -> NO (source reading, no run needed)

FEBio = config.json febio_src, FEBioMech/.

1. FESolidSolver2::Quasin -> PrepStep() (FESolidSolver2.cpp:1046) -> UpdateModel() (:962) with m_niter == 0, positions = last
   converged state.
2. -> FESlidingElasticInterface::Update() (FESlidingElasticInterface.cpp:650):
   - :680 ProjectSurface(m_ss, m_ms, ...): for every integration point data.m_rs = current ray projection (:596-597, :610-611),
     unconditionally (also for points that were stuck).
   - :685-688 only AFTER that, if m_niter == 0: InitSlidingSurface() -> data.m_rsp = data.m_rs (:136), i.e. the CURRENT projection.
3. Inside the increment ContactTraction (:857-885) uses m_rsp as the stick point and, while stuck, sets m_rs = m_rsp (:881):
   memory only WITHIN one increment.
=> At each increment start FEBio's stick point = projection of the converged position: the elastic tangential offset is
   forgotten. This is exactly the "legacy rule" in gpufe/gate1d_stick_memory.py:37-39, not the rule now in contact.py:106-114.
Empirical confirmation (r0001, this folder): v02_results_E10.json - FEBio creeps 0.0151 mm per hold increment under a constant
sub-limit shear (0.075 mm with 5 hold increments, 0.302 mm with 20); GPU (old rule) 0.0075 mm per increment.
Consequence: after the F-0003 fix the GPU solver is physically better than FEBio (Coulomb stick does not creep) but no longer
matches FEBio for holds / cycles. FEBio cannot be the reference for gate 4 hold / cyclic quantities.
